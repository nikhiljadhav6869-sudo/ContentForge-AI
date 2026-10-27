# Free public portfolio demo

Use the root `Dockerfile` to run ContentForge AI as a single-container Docker Space on Hugging Face. This profile runs Next.js, FastAPI, SQLite, and the local workflow executor together. It does not need PostgreSQL, Redis, a purchased domain, paid AI keys, or SMTP.

Choose **CPU Basic only if the creation screen shows $0/free**. Do not enable paid hardware or persistent storage. Provider offerings can change; the hosting documentation could not be fetched from this development environment on 27 October 2026, so current pricing and account eligibility have not been independently verified. References: [Spaces overview](https://huggingface.co/docs/hub/spaces-overview) and [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker).

This is a portfolio/demo deployment. It uses curated sample outputs with real orchestration, evidence review, editing, approval, and export. It does not generate new content with a live language model. Free hosting can sleep or reset its disk. Export work before leaving and use sample content rather than private documents. The full persistent deployment remains documented in [DEPLOYMENT.md](DEPLOYMENT.md).

## Create the Space without a terminal

1. Create or sign in to a [Hugging Face account](https://huggingface.co/join).
2. Open [Create a new Space](https://huggingface.co/new-space). Choose your account as owner and name it `contentforge-ai`.
3. Select **Docker**, then the **Blank** template if offered. Choose **Public** visibility and the CPU option explicitly marked **free/$0**. Do not select a GPU, paid upgrade, or paid storage.
4. Download [the GitHub source ZIP](https://github.com/nikhiljadhav6869-sudo/ContentForge-AI/archive/refs/heads/main.zip) and extract it on your computer. Use the files *inside* the extracted `ContentForge-AI-main` folder.
5. In your new Space, open **Files → Add file → Upload files**. Upload the repository contents while preserving the folder structure. The Space root must contain `README.md`, `Dockerfile`, `.dockerignore`, `backend/`, `frontend/`, and `deploy/space/start.py`. Do not upload the enclosing `ContentForge-AI-main` folder or the ZIP as a single file. Replace the template README with this repository's README; its metadata selects Docker and port 7860.
6. Commit the upload. Open the build logs and wait for **Running**. The first build installs frozen Python/npm dependencies and builds the frontend.
7. Open the Space's **direct app URL**, normally `https://<your-space-host>.hf.space`, in a new browser tab. Use the URL shown by Hugging Face rather than guessing it. Direct access avoids browsers blocking login cookies inside an embedded cross-site frame.
8. Choose **Explore the live demo**. Inspect the agents and evidence, edit a draft, approve the campaign, and download its ZIP package. Add the direct app URL to your GitHub repository's **About → Website** field.

Do not add API keys or mail credentials. This image forces demo-only operation and clears those settings even if they are accidentally supplied. Account registration is disabled; visitors use separate guest sessions. Each workspace gets ten generation admissions per UTC day and one active workflow. Login/write limits apply to the internal web proxy as a shared allowance on this small deployment; it is intended for light demo traffic.

Hugging Face normally supplies `SPACE_HOST`. If startup reports an invalid host or browser writes fail because the origin does not match, open **Settings → Variables and secrets** and set the non-secret variable `SPACE_HOST` to the exact hostname from the direct app URL, for example `yourname-contentforge-ai.hf.space`, without `https://`, a path, or a port. Do not change the app to accept arbitrary browser origins. `DEMO_LOCAL_ORIGIN` is only for local testing and must not be set for the hosted Space.

## Upload with Git instead

After creating the empty Space, make a separate checkout and push to it:

```bash
git clone https://github.com/nikhiljadhav6869-sudo/ContentForge-AI.git contentforge-space-upload
cd contentforge-space-upload
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/contentforge-ai
git fetch space main
git merge --allow-unrelated-histories -s ours space/main -m "Initialize ContentForge demo Space"
git push space main
```

Replace `YOUR_USERNAME`. The merge is intended only for the newly created, empty/template Space: it retains the complete ContentForge tree while recording the template commit as history. Do not use this procedure to replace a Space containing other work. Authenticate through your credential manager or the interactive Git prompt using an appropriately scoped Hugging Face write token. Never put a token in the URL, shell history, README, or GitHub repository. No access token is required to run the resulting public demo.

## Verify the same image locally

```bash
docker build -t contentforge-space .
docker run --rm --name contentforge-space-demo -p 127.0.0.1:7860:7860 contentforge-space
```

Open `http://localhost:7860`. No volume is attached, so stopping/removing this test container discards its demo database. To use another host port, also provide a matching loopback origin:

```bash
docker run --rm --name contentforge-space-demo \
  -p 127.0.0.1:7861:7860 \
  -e DEMO_LOCAL_ORIGIN=http://localhost:7861 contentforge-space
python3 scripts/smoke.py --base-url http://localhost:7861
```

Only the frontend listens publicly. The API binds to container loopback, ignores forwarded client headers, and receives requests through the frontend's same-origin rewrite. In a Space, the host supplies HTTPS and the app uses secure session cookies. The launcher applies migrations, waits for API readiness, and stops both services if either exits. Live provider calls are also rejected inside the gateway, including calls from resumed workflows.

This image has been prepared for deployment; a public Space still requires your account and upload. A passing local container test does not verify the hosting account, current free-tier availability, public TLS, sleep/wake behavior, or hosting quotas. Long-term storage, unattended backups, live AI, transactional mail, and production uptime are outside this free demo profile.
