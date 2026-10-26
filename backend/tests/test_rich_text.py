import copy
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import Session, ArtifactVersion
from app.rich_text import validate_document, document_text, document_markdown


def paragraph(text, marks=None):
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text, **({"marks": [{"type": m} for m in marks]} if marks else {})}],
    }


def document():
    return {
        "type": "doc",
        "content": [
            paragraph("Battery electric vehicles produce no tailpipe emissions.", ["bold"]),
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [paragraph("Review the source evidence before sharing.", ["italic"])],
                    }
                ],
            },
        ],
    }


def edit(client, run, doc=None):
    artifact = run["artifacts"][0]
    version = max((v for v in run["versions"] if v["artifact_id"] == artifact["id"]), key=lambda v: v["number"])
    doc = doc or document()
    return client.put(
        f"/api/artifacts/{artifact['id']}",
        json={"body": document_text(doc), "document": doc, "base_version": version["number"]},
    )


def test_formatting_persists_in_new_version_with_correct_claim_offsets_and_approved_exports(client, campaign):
    original = copy.deepcopy(campaign)
    response = edit(client, campaign)
    assert response.status_code == 200, response.text
    version = response.json()
    assert version["document"] == document()
    assert version["body"] == document_text(document())
    run = client.get(f"/api/workflows/{campaign['id']}").json()
    claims = [c for c in run["claims"] if c["version_id"] == version["id"]]
    assert claims and all(c["status"] == "unverified" for c in claims)
    assert all(version["body"][c["start"] : c["end"]] == c["text"] for c in claims)
    assert all(v in run["versions"] for v in original["versions"])
    with Session() as db:
        assert db.get(ArtifactVersion, version["id"]).document == document()
    assert (
        client.post(
            f"/api/workflows/{campaign['id']}/review", json={"decision": "approve", "acknowledge_warnings": True}
        ).status_code
        == 200
    )
    prefix = f"/api/workflows/{campaign['id']}/export"
    data = client.get(prefix, params={"format": "json"}).json()
    assert version in [a["version"] for a in data["artifacts"]]
    markdown = client.get(prefix).text
    assert "**Battery electric vehicles" in markdown and "- *Review the source evidence" in markdown
    archive = zipfile.ZipFile(io.BytesIO(client.get(prefix, params={"format": "zip"}).content))
    assert archive.read("campaign.md").decode() == markdown
    assert version in [a["version"] for a in json.loads(archive.read("campaign.json"))["artifacts"]]
    assert edit(client, run).status_code == 409


def test_plain_edits_remain_compatible_and_formatting_never_leaks_to_later_plain_versions(client, campaign):
    rich = edit(client, campaign).json()
    response = client.put(
        f"/api/artifacts/{rich['artifact_id']}",
        json={"body": rich["body"] + "\n\nPlain text version.", "base_version": rich["number"]},
    )
    assert response.status_code == 200 and response.json()["document"] is None
    with Session() as db:
        assert db.get(ArtifactVersion, rich["id"]).document == document()


def test_stale_edits_and_other_workspaces_cannot_change_formatting(client, campaign):
    saved = edit(client, campaign).json()
    assert edit(client, campaign).status_code == 409
    other = TestClient(app)
    other.post("/api/auth/demo")
    assert edit(other, campaign).status_code == 404
    with Session() as db:
        assert db.get(ArtifactVersion, saved["id"]).document == document()
        assert (
            len(list(db.scalars(select(ArtifactVersion).where(ArtifactVersion.artifact_id == saved["artifact_id"]))))
            == saved["number"]
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "script", "content": []},
        {"type": []},
        {"type": "doc", "attrs": {"onclick": "alert(1)"}, "content": [paragraph("Valid content.")]},
        {"type": "doc", "content": [{"type": "image", "attrs": {"src": "javascript:alert(1)"}}]},
        {"type": "doc", "content": [paragraph("Bad link text.", ["link"])]},
        {"type": "doc", "content": [paragraph("Duplicate marks.", ["bold", "bold"])]},
        {"type": "doc", "content": [paragraph("Malformed mark.", [[]])]},
        {"type": "doc", "content": [{"type": "listItem", "content": [paragraph("Bad root item.")]}]},
        {"type": "doc", "content": [{"type": "bulletList", "content": [paragraph("Bad list child.")]}]},
        {"type": "doc", "content": []},
    ],
)
def test_invalid_or_unsafe_document_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_document(bad)


def test_mismatched_text_is_rejected_without_creating_a_version(client, campaign):
    artifact = campaign["artifacts"][0]
    version = max(v["number"] for v in campaign["versions"] if v["artifact_id"] == artifact["id"])
    result = client.put(
        f"/api/artifacts/{artifact['id']}",
        json={"body": "A different visible claim.", "document": document(), "base_version": version},
    )
    assert result.status_code == 422
    assert client.get(f"/api/workflows/{campaign['id']}").json()["versions"] == campaign["versions"]


def test_complexity_and_text_bounds_are_enforced():
    deep = paragraph("Nested text.")
    for _ in range(12):
        deep = {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraph("Parent."), deep]}]}
    for bad in [
        {"type": "doc", "content": [deep]},
        {"type": "doc", "content": [paragraph("word")] * 5001},
        {"type": "doc", "content": [paragraph("x" * 30000), paragraph("y" * 30000)]},
    ]:
        with pytest.raises(ValueError):
            validate_document(bad)


def test_nested_lists_breaks_unicode_and_literal_html_have_canonical_text_and_safe_markdown():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "नमस्ते <script>alert(1)</script>"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "[click](javascript:alert(1))"},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            paragraph("Parent", ["bold", "italic"]),
                            {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraph("Child")]}]},
                        ],
                    }
                ],
            },
        ],
    }
    valid = validate_document(doc)
    assert document_text(valid) == "नमस्ते <script>alert(1)</script>\n[click](javascript:alert(1))\n\nParent\n\nChild"
    markdown = document_markdown(valid)
    assert "<script>" not in markdown and "&lt;script&gt;" in markdown
    assert "\\[click\\]" in markdown and "- ***Parent***\n  \n  - Child" in markdown
