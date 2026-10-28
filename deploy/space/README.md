---
title: ContentForge AI
emoji: ✍️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Multi-agent content workflow with evidence and human review
---

# Standalone Docker demo

This metadata is for a Docker-capable host, not a free Static Space. The user’s Hugging Face creation screen on 28 October 2026 requires a paid plan for Docker. Do not replace a Static Space's README with this file unless you deliberately choose Docker hosting and accept its charges. For the free public showcase, use [deploy/static](../static/README.md).

To run the full no-key demo on your computer, from the repository root:

```bash
docker build -t contentforge-demo .
docker run --rm -p 127.0.0.1:7860:7860 contentforge-demo
```

Open http://localhost:7860. The image runs Next.js and a loopback FastAPI server, SQLite, and the local workflow executor under an unprivileged user. It disables live AI, email, and account registration; visitors use guest sessions. Stopping this `--rm` container removes its temporary database, so export your work first.

On a Docker Space available under your chosen plan, upload the repository runtime files and root Dockerfile, then use this file as the Space's root README. The launcher expects `SPACE_HOST` to be the exact direct hostname ending in `.hf.space`, without a scheme or path. Open the direct app URL to avoid third-party iframe-cookie restrictions. Do not add API keys or SMTP credentials: this image clears them and enforces demo-only generation.

For local testing on another port, set `DEMO_LOCAL_ORIGIN=http://localhost:7861` alongside `-p 127.0.0.1:7861:7860`. Only loopback HTTP origins are accepted for this override. On hosting, use `SPACE_HOST` instead. The regular persistent deployment remains described in the root DEPLOYMENT.md.
