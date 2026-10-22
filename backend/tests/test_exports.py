import hashlib
import io
import json
from pathlib import PurePosixPath
import zipfile

import pytest

from app.db import Session, ContentArtifact
from app.exports import campaign_zip
from app.traceability import new_version


def approve(client, run_id):
    response = client.post(
        f"/api/workflows/{run_id}/review",
        json={"decision": "approve", "acknowledge_warnings": True, "comment": "Reviewed for package export."},
    )
    assert response.status_code == 200, response.text


def test_zip_contains_only_approved_versions_and_linked_evidence(client, campaign):
    endpoint = f"/api/workflows/{campaign['id']}/export"
    assert client.get(endpoint, params={"format": "zip"}).status_code == 409
    approve(client, campaign["id"])
    response = client.get(endpoint, params={"format": "zip"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == 'attachment; filename="contentforge-campaign.zip"'
    assert response.content == client.get(endpoint, params={"format": "zip"}).content

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        payload = json.loads(archive.read("campaign.json"))
        evidence = json.loads(archive.read("evidence.json"))
        assert payload == client.get(endpoint, params={"format": "json"}).json()
        assert archive.read("campaign.md").decode() == client.get(endpoint).text
        approved = set(payload["approval"]["version_ids"])
        assert set(evidence["approved_version_ids"]) == approved
        assert {item["version_id"] for item in manifest["artifacts"]} == approved
        assert len(manifest["artifacts"]) == 4
        assert set(archive.namelist()) == {"manifest.json", *(item["path"] for item in manifest["files"])}
        for item in manifest["files"]:
            content = archive.read(item["path"])
            assert item["bytes"] == len(content)
            assert item["sha256"] == hashlib.sha256(content).hexdigest()
        for item in manifest["artifacts"]:
            artifact = next(a for a in payload["artifacts"] if a["id"] == item["artifact_id"])
            document = archive.read(item["path"]).decode()
            assert artifact["version"]["body"] in document and "DEMO:" in document
        assert "DEMO:" in archive.read("README.md").decode()
        assert "not a factual guarantee" in archive.read("campaign.md").decode()
        assert evidence["claims"] and evidence["links"] and evidence["sources"]
        assert {c["version_id"] for c in evidence["claims"]} <= approved
        claims = {c["id"] for c in evidence["claims"]}
        passages = {p["id"]: p for p in evidence["passages"]}
        assert {link["passage_id"] for link in evidence["links"]} == set(passages)
        assert {p["source_id"] for p in passages.values()} == {s["id"] for s in evidence["sources"]}
        assert all("text" not in source and "workspace_id" not in source for source in evidence["sources"])
        for link in evidence["links"]:
            assert link["claim_id"] in claims
            assert link["quote"] in passages[link["passage_id"]]["text"]
        for old in campaign["versions"]:
            if old["id"] not in approved:
                assert old["id"] not in archive.read("campaign.json").decode()
                assert old["id"] not in archive.read("evidence.json").decode()
    assert client.get(endpoint, params={"format": "unsupported"}).status_code == 400


@pytest.mark.parametrize("format", ["markdown", "json", "zip"])
def test_exports_reject_versions_changed_after_approval(client, campaign, format):
    approve(client, campaign["id"])
    # Simulate an inconsistent writer bypassing the public edit guard.
    with Session.begin() as db:
        artifact = db.get(ContentArtifact, campaign["artifacts"][0]["id"])
        new_version(db, artifact, "This replacement has never been approved.", "Regression fixture")
    result = client.get(f"/api/workflows/{campaign['id']}/export", params={"format": format})
    assert result.status_code == 409 and result.json()["detail"] == "Current versions are not approved."


def test_zip_paths_are_safe_unique_and_preserve_unicode():
    payload = {
        "run_id": "run",
        "mode": "demo",
        "claims": [],
        "approval": {"id": "approval", "created_at": "2026-10-22T00:00:00+00:00"},
        "artifacts": [
            {
                "id": str(index),
                "platform": "../../outside\\document",
                "title": "/tmp/overwrite",
                "version": {"id": f"version-{index}", "number": 1, "body": "नमस्ते — evidence matters."},
            }
            for index in range(2)
        ],
    }
    with zipfile.ZipFile(io.BytesIO(campaign_zip(payload, {"claims": [], "links": []}))) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for name in archive.namelist():
            path = PurePosixPath(name)
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in name
        documents = [name for name in archive.namelist() if name.startswith("content/")]
        assert len(documents) == 2
        assert all("नमस्ते" in archive.read(name).decode("utf-8") for name in documents)
