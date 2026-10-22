# Viva guide

**What problem does the project solve?**
It combines content production and evidence accountability. Users can watch specialized tasks execute and trace a sentence in a final artifact back to source material, agent execution, prior versions, and a human decision.

**Why multiple agents instead of one prompt?**
Roles have separate inputs, instructions, outputs, records, and error boundaries. Research and strategy can run concurrently. Writing, evidence checking, and editing have distinct responsibilities. Quality can route a targeted revision, and export cannot bypass approval.

**Why LangGraph?**
The workflow has parallel branches, a join, conditional revision edges, bounded loops, persistent checkpoints, and a human interrupt. A state graph makes these dependencies and recovery points explicit.

**Are they truly autonomous?**
They act within a bounded application workflow. They cannot grant themselves tools, read credentials, publish externally, or execute arbitrary code. The server controls routing and permissions.

**How do agents communicate?**
A typed state carries the brief, accumulated role results, revision budget, and routing flag. Artifacts and source passages are persisted in relational storage. The graph passes the relevant context to each stage.

**How is the graph live?**
Agents emit database events around real work. An atomic per-run sequence orders them. FastAPI streams them with SSE, and the frontend refreshes authoritative run data. Reconnection replays missed events.

**Is evidence verification infallible?**
No. Automatic support is intentionally conservative: exact text in a stored source. The extractor is heuristic, the source may itself be wrong, and a statement can require context. The UI distinguishes support, dispute, and uncertainty and exposes the quote for review.

**How is the demo honest?**
It uses labeled fixture outputs and local sample references, but executes the real graph, records real durations and events, performs a revision, pauses for approval, and exports real stored artifacts. It does not claim live AI research or fabricated token usage.

**What if the server crashes?**
Database events and LangGraph checkpoints survive. Local mode marks abandoned runs interrupted; the owner can retry the saved checkpoint. Redis/RQ handles queued work in deployment. Side effects near crash boundaries can be at-least-once; the project does not promise exactly-once provider billing.

**How are edits handled?**
An edit creates a new immutable artifact version. Its claims are re-extracted and marked unverified. Older source links and review records remain attached to older versions. Export checks the exact approved version IDs.

**How are credentials protected?**
Keys are backend environment variables. The gateway emits sanitized errors and metrics, never keys. Passwords use salted scrypt, sessions use random opaque cookies stored as hashes, and every resource is checked against workspace ownership.

**What is the quality score?**
An explainable heuristic: factual support 25%, relevance 20%, clarity 15%, structure 15%, brand consistency 10%, platform suitability 10%, engagement 5%. Its basis is displayed. Scores never erase evidence warnings.

**What remains to improve?**
Semantic claim extraction and entailment validation, authoritative source retrieval/search, stronger evaluator calibration, rich-text serialization, accessibility auditing, shared-workspace roles, public deployment rate limiting, and authorized publishing integrations. Live-model behavior must be tested against the chosen provider and model.
