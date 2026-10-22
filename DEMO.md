# College presentation walkthrough

## Preparation

Start the application using the README instructions. No paid AI account is needed. Demo sign-in creates an isolated guest workspace and a session cookie. Keep the same browser session, or create a password account if you want to return later.

The demo is an actual LangGraph execution with persistent events and sample data, not live model generation. It always demonstrates the EV campaign; connecting a model enables arbitrary topics.

## Five-minute journey

1. On the landing page, click **Explore the live demo**.
2. In **Agent Control Center**, observe research and strategy running in parallel, then the remaining stages. Select a node to see inputs, outputs, safe decision summaries, and timings. Demo token/cost metrics are unavailable rather than fabricated.
3. The first draft contains a lifecycle overclaim and an unsupported 900-kilometre range claim. The quality stage routes a bounded revision back to the writer. The graph shows a feedback edge and the event log preserves both rounds.
4. Open **Evidence intelligence**. Select a green-underlined claim to see two supporting sample documents. Switch to **Version 1**, then select the lifecycle claim to inspect its contradictory passage. The source cards, relationships, and exact quotes all refer to stored data.
5. Open **Content studio**. Switch among blog, LinkedIn, Instagram, and YouTube outputs. Compare the two versions. Optionally edit text and save; the new version’s claims become unverified. Select text and add an anchored comment.
6. Inspect evidence and remaining warnings. Check the acknowledgement box if required, add review notes, and click **Approve current versions**. A human decision resumes the graph and the export agent packages the approved versions.
7. Click **Download ZIP package**. Open an approved document in `content/`, inspect `evidence.json`, and show the version IDs and file checksums in `manifest.json`. Markdown, JSON, and the full execution report remain available separately. The exports disclose demo mode.
8. Visit **Agent analytics** for real measured stage durations and the quality rubric. Add an approved artifact to **Publishing calendar**. Explain that this is an editorial reminder, not automatic social publication.

## Useful talking points

- A workflow graph coordinates specialized responsibilities; it is not a single chat prompt disguised as ten animations.
- The frontend reflects persisted backend events and reconnects with a sequence cursor.
- Evidence support and source credibility are separate concepts.
- Human review is a real checkpoint, not a decorative button.
- Original drafts, revisions, reviewer decisions, and source passages remain inspectable.

For a live-model presentation, configure a server provider, upload trustworthy sources, select that provider in Workflow Studio, and run a small campaign first. This requires a separate connectivity and quality check; a successful demo does not prove a live provider works.
