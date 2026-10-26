"""Portable packages containing only the versions pinned by human approval."""

import hashlib
import io
import json
import re
import zipfile
from .rich_text import document_markdown

DEMO_NOTICE = "DEMO: generated from labeled sample fixtures. Not live AI research."
EVIDENCE_NOTICE = "Human approval is an editorial decision, not a factual guarantee."


def json_document(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def artifact_markdown(artifact, mode):
    version = artifact["version"]
    disclaimer = DEMO_NOTICE + "\n\n" if mode == "demo" else ""
    content = document_markdown(version["document"]) if version.get("document") else version["body"]
    return disclaimer + f"# {artifact['platform'].upper()} · v{version['number']}\n\n{content}"


def campaign_markdown(payload):
    data = "\n\n---\n\n".join(artifact_markdown(artifact, payload["mode"]) for artifact in payload["artifacts"])
    data += "\n\n## Evidence audit\n\n" + "\n".join(
        f"- [{claim['status']}] {claim['text']}" for claim in payload["claims"]
    )
    return (
        data
        + "\n\n"
        + EVIDENCE_NOTICE
        + " See the evidence or execution report for source passages and relationships.\n"
    )


def campaign_zip(payload, evidence):
    files = {
        "campaign.md": campaign_markdown(payload),
        "campaign.json": json_document(payload),
        "evidence.json": json_document(evidence),
        "README.md": (
            "# ContentForge AI campaign package\n\n"
            + (DEMO_NOTICE + "\n\n" if payload["mode"] == "demo" else "")
            + "- `content/`: one Markdown document per approved content format.\n"
            "- `campaign.md`: combined approved drafts and evidence statuses.\n"
            "- `campaign.json`: exact approved versions, claims, and the approval record.\n"
            "- `evidence.json`: linked quotes, stored passages, and source metadata for those versions.\n"
            "- `manifest.json`: version IDs, file sizes, and SHA-256 hashes.\n\n"
            + EVIDENCE_NOTICE
            + " A supported claim has textual evidence, not independently certified truth.\n\n"
            "The evidence file includes source excerpts. Review their contents before sharing this archive. "
            "Unlinked passages, earlier drafts, and internal execution logs are not included. "
            "Source content hashes identify the original stored source, not just the excerpt.\n\n"
            "Manifest hashes detect file changes relative to the manifest; they are not digital signatures. "
            "The manifest itself is not included in its file list.\n"
        ),
    }
    artifacts = []
    for index, artifact in enumerate(payload["artifacts"], 1):
        # Titles and source filenames never control archive paths.
        slug = re.sub(r"[^a-z0-9]+", "-", artifact["platform"].lower()).strip("-")[:40] or "content"
        path = f"content/{index:02d}-{slug}.md"
        files[path] = artifact_markdown(artifact, payload["mode"]) + "\n"
        artifacts.append(
            {
                "artifact_id": artifact["id"],
                "version_id": artifact["version"]["id"],
                "version_number": artifact["version"]["number"],
                "platform": artifact["platform"],
                "path": path,
            }
        )
    encoded = {path: content.encode("utf-8") for path, content in files.items()}
    manifest = {
        "schema_version": 1,
        "run_id": payload["run_id"],
        "mode": payload["mode"],
        "approval_id": payload["approval"]["id"],
        "approved_at": payload["approval"]["created_at"],
        "artifacts": artifacts,
        "files": [
            {"path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(encoded.items())
        ],
    }
    encoded["manifest.json"] = json_document(manifest).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in sorted(encoded.items()):
            # Fixed archive metadata makes repeat downloads of the same snapshot reproducible.
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()
