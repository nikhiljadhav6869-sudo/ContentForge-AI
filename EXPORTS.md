# Export a campaign package

1. Open **Content Studio** for a campaign.
2. Review the current drafts and evidence warnings, then approve the versions.
3. Wait for **Approved and ready for your next step**.
4. Choose **Download ZIP package** and extract the downloaded archive.

You can make ZIP the default for **Export campaign** in **Settings → Preferred export format**. Markdown and JSON remain available.

## Package contents

```text
contentforge-campaign.zip
├── README.md
├── campaign.md
├── campaign.json
├── evidence.json
├── manifest.json
└── content/
    ├── 01-blog.md
    ├── 02-instagram.md
    ├── 03-linkedin.md
    └── 04-youtube.md
```

The `content/` directory contains the formats requested for that campaign. Each file contains its approved version, with a demonstration label when applicable. `campaign.md` combines those drafts and their claim statuses. `campaign.json` records the exact versions, claims, and human approval.

`evidence.json` contains claims for the approved versions, their evidence relationships, linked stored passages, and source metadata. A claim without evidence remains visible with its warning. Source metadata retains the original document hash; full source documents and unlinked passages are omitted. Earlier draft versions and internal execution logs are available separately through the execution report in the app.

The package contains reference excerpts and reviewer identifiers. Review the contents before sharing it. Human approval and textual support do not independently establish factual truth.

## Integrity and reproducibility

`manifest.json` uses schema version 1. It identifies the workflow, mode, approval ID and time, and each exported artifact's version and path. Its file list contains the byte length and SHA-256 hash of every other archive member. The manifest does not hash itself.

To verify a file after extraction, hash its original bytes and compare the result with its manifest entry. Editing a file, including its line endings, changes its hash. These hashes detect changes relative to the manifest; they are not a signature or proof of who created the package.

Archive paths are generated from a numeric position and a sanitized format name. User titles and uploaded filenames do not control paths. ZIP entry dates are fixed for reproducible downloads; the approval timestamp in the manifest is the actual recorded approval time.

## API

```text
GET /api/workflows/{run_id}/export?format=zip
```

The authenticated owner receives `application/zip` with the filename `contentforge-campaign.zip`. The endpoint uses the same approval checks as Markdown and JSON: execution must be completed and the current version set must exactly match the approval record. A missing or outdated approval returns HTTP 409. Another workspace cannot download the campaign.
