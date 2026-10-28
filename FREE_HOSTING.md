# Free Static Space showcase

The user’s Hugging Face creation screen on **28 October 2026** explicitly marks Docker and Gradio Spaces as requiring a paid plan and Static Spaces as free. This supersedes the previous Docker-based free-hosting suggestion. Do not subscribe to PRO for the zero-budget setup.

A Static Space can display the project showcase in `deploy/static/index.html`. It cannot run ContentForge's Python backend, database, workflow executor, authentication, or live AI. The page clearly states that limitation, explains the implementation, links to GitHub, and gives instructions for running the full no-key demo on your computer.

## Update the existing NJ027/contentforge-ai Space

1. Open [the prepared HTML source](https://raw.githubusercontent.com/nikhiljadhav6869-sudo/ContentForge-AI/main/deploy/static/index.html) in a new browser tab. Click inside the text, press **Ctrl+A**, then **Ctrl+C**.
2. Return to the Space's **Files → index.html** page and click **Edit** (the pencil icon).
3. Click inside the code editor, press **Ctrl+A**, then **Ctrl+V** to replace the starter HTML completely.
4. Enter **Add ContentForge AI showcase** as the commit message and commit directly to `main`.
5. Open the **App** tab and refresh. You should see the ContentForge AI showcase rather than the default welcome page.

The page includes all of its styling. No `style.css`, images, JavaScript, installation, keys, or extra service is required. An existing starter `style.css` can remain; this HTML does not load it.

Keep the Space's README configured with `sdk: static` and `app_file: index.html`. Do not upload the root Dockerfile, backend/frontend application directories, or the Docker profile README to this Static Space. A correct optional static README is provided at `deploy/static/README.md`; it only needs uploading if the existing Space metadata is incorrect.

If raw GitHub source does not open, visit [the file on GitHub](https://github.com/nikhiljadhav6869-sudo/ContentForge-AI/blob/main/deploy/static/index.html), select **Raw**, and copy its contents. Alternatively, download that one file and use **Files → Add file → Upload files** to replace the Space-root `index.html`.

## Run the full software for no service fee

Install Git and Docker with Linux containers, then run:

```bash
git clone https://github.com/nikhiljadhav6869-sudo/ContentForge-AI.git
cd ContentForge-AI
docker build -t contentforge-demo .
docker run --rm -p 127.0.0.1:7860:7860 contentforge-demo
```

Open http://localhost:7860 and choose **Explore the live demo**. This runs the full workflow with labeled sample outputs and no paid model calls. Data in this temporary container is removed when it stops; export work first. Hardware, electricity, and Internet access are supplied by your own computer. A local run does not create a publicly available full-app service.

See [the Docker profile](deploy/space/README.md) for that container's settings and [DEPLOYMENT.md](DEPLOYMENT.md) for the full persistent deployment. No paid hosting has been purchased or enabled here.
