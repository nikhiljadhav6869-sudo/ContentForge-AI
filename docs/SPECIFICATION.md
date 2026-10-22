# CODEX ASTRA — ULTRA MASTER BUILD PROMPT
## CONTENTFORGE AI — Premium Multi-Agent Content Intelligence Platform

### 1. YOUR ROLE AND MISSION

Act as a senior full-stack architect, AI/ML engineer, LangGraph specialist, creative frontend designer, product engineer, and QA lead.

Build a complete, production-oriented project called:

**CONTENTFORGE AI — Autonomous Multi-Agent Content Intelligence Platform**

Tagline: **From an idea to verified content. Powered by collaborating AI agents.**

The product must have two flagship innovations:

1. **Live Multi-Agent Control Center**
2. **Evidence-to-Content Traceability Engine**

These must be the most technically sophisticated and visually impressive features.

Do not build a generic chatbot, static workflow animation, simple content generator, or dashboard with disconnected mock data.

Create a working application with:
- Beautiful premium frontend.
- Functional backend.
- Multi-agent orchestration.
- Real-time execution visualization.
- Source-backed content generation.
- Agent communication and decision traces.
- Human approval workflow.
- Persistent database.
- Multiple content formats.
- Functional demo mode.
- Tests and deployment setup.

**Important:** A visually impressive interface is necessary, but real technical functionality is equally important.

---

# 2. PRODUCT EXPERIENCE

The application should transform one user instruction into a complete, research-backed content campaign.

Example:

"Create an educational campaign about artificial intelligence in healthcare for Indian college students. Generate a blog, LinkedIn post, Instagram caption, and YouTube script."

Expected operation:

1. Supervisor Agent understands the request.
2. Strategy Agent creates the content strategy.
3. Research Agent collects relevant information.
4. Writer Agent generates content.
5. Fact-Checking Agent evaluates factual claims.
6. Editor Agent improves content quality.
7. Brand Agent checks writing tone.
8. SEO Agent adapts content for each platform.
9. Quality Agent evaluates the outputs.
10. Human reviewer approves the content.
11. Export Agent prepares final deliverables.

The user must be able to observe the agents executing inside a visual command center.

---

# 3. TECHNOLOGY STACK

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Motion animations
- React Flow / XYFlow
- Lucide icons
- Recharts
- TanStack Query
- Zustand for local UI state
- Monaco Editor or a capable rich-text editor where appropriate

### Backend
- Python 3.12+
- FastAPI
- LangGraph
- LangChain model adapters where appropriate
- Pydantic
- SQLAlchemy
- PostgreSQL
- Alembic
- Redis
- Background task queue
- Server-Sent Events for live execution events

### AI Providers
Support:
- OpenAI-compatible APIs
- Google Gemini
- Ollama local models

Implement a configurable model gateway with retries, timeouts, cost tracking, and rate-limit handling.

Do not expose API keys in browser code.

### Deployment
- Docker Compose for local development
- Vercel-compatible frontend
- Containerized backend deployment
- Environment examples
- Health checks
- Automated build validation

Choose compatible dependency versions and verify them during installation.

---

# 4. PREMIUM DESIGN SYSTEM

The frontend must be exceptionally attractive.

## Design inspiration

Draw inspiration from:
- Linear's clarity and polished transitions.
- Vercel's refined dark interface.
- Figma's professional canvas interactions.
- Raycast's command-driven productivity.
- Modern AI observability dashboards.
- Apple-inspired micro-interactions.

Create an original product identity. Do not blindly clone existing interfaces.

## Visual direction

Premium dark futuristic aesthetic.

### Suggested colors

Background: #080B12
Sidebar: #0D111B
Panels: #121826
Elevated surfaces: #192235
Primary text: #F5F7FF
Secondary text: #96A4BE
Electric blue: #68B7FF
Soft violet: #A78BFA
Teal: #42D6C4
Success: #4ADE80
Warning: #FBBF24
Error: #FB7185

Use gradients sparingly and purposefully.

### Design requirements

- Subtle glassmorphism.
- Elegant borders and shadows.
- Beautiful card layouts.
- Gradient highlights.
- Smooth hover states.
- Animated counters.
- Carefully selected typography.
- Consistent spacing.
- Responsive layout.
- Skeleton loading.
- Toast notifications.
- Keyboard navigation.
- Accessible contrast.
- Reduced-motion support.
- No unnecessary glowing elements.
- No overlapping or clipped components.

Use distinctive icons and small visual indicators throughout the application.

The overall result should feel like a polished commercial SaaS product.

---

# 5. SIGNATURE FEATURE ONE
## LIVE MULTI-AGENT CONTROL CENTER

Build a dedicated screen called:

**Agent Control Center**

This screen should be the primary visual attraction of the entire application.

### Overall layout

Create a three-panel professional workspace.

**LEFT SIDEBAR**
- Project information.
- Workflow navigation.
- Agent directory.
- Saved workflows.
- Workflow history.
- Quick access to settings.

**CENTER CANVAS**
- Interactive agent orchestration graph.
- Animated connections.
- Execution states.
- Dynamic routing.
- Zoom and pan.
- Selected agent details.
- Visual decision branches.

**RIGHT INSPECTOR**
- Agent details.
- Live activity stream.
- Input/output preview.
- Agent decisions.
- Evidence and tool calls.
- Execution metrics.
- Errors and retries.

Add a collapsible bottom terminal panel for real-time event logs.

### Agent graph

Use React Flow to display agents as beautifully designed nodes.

Each node should contain:
- Agent icon.
- Agent name.
- Current task summary.
- Execution status.
- Processing duration.
- Input/output indicators.
- Error or warning count.

### Agent states

Waiting:
Neutral gray node.

Running:
Blue/violet glowing border with subtle pulse animation.

Completed:
Green success accent and checkmark.

Failed:
Red accent and actionable error indicator.

Needs human review:
Amber highlight and approval icon.

### Graph animation

When an agent starts:
- Its node illuminates.
- An animated signal moves along the active connection.
- The inspector displays its current activity.
- Relevant metrics update.
- The bottom log receives events.

When an agent completes:
- Its node changes state.
- Completion time becomes visible.
- A structured result is saved.
- The next executable tasks are highlighted.

When the Quality Agent requests a revision:
- The graph must show a visible feedback edge.
- The responsible agent should receive the revision.
- The revision count should update.

Avoid generic looping animations that misrepresent actual execution.

### Agent detail drawer

Clicking an agent must open a detailed view displaying:

**Overview**
- Role.
- Model.
- Task description.
- Status.
- Duration.

**Inputs**
- Source context.
- Previous agent outputs.
- User constraints.

**Outputs**
- Structured generated results.
- Content previews.
- Warnings.

**Decision Trace**
- Received task.
- Tools invoked.
- Returned observations.
- Decision summary.
- Next routing action.

Do not display fabricated hidden model chain-of-thought. Show observable events and structured decision summaries generated specifically for the application.

**Metrics**
- Input tokens.
- Output tokens.
- Latency.
- Estimated cost.
- Retries.
- Error counts.

Only show real metrics when available; otherwise label estimated or unavailable.

### Live activity stream

Example event entries:

10:24:03 — Supervisor created workflow plan.
10:24:05 — Research Agent started source collection.
10:24:12 — Research Agent extracted 6 relevant sources.
10:24:13 — Strategy Agent finalized campaign outline.
10:24:17 — Writer Agent generated first draft.
10:24:20 — Fact Checker flagged 2 unsupported claims.
10:24:23 — Writer Agent received revision request.
10:24:29 — Fact Checker approved revised claims.
10:24:35 — Quality Agent completed evaluation.
10:24:36 — Workflow awaiting human approval.

These are examples only. In real mode, all event rows must come from actual backend events.

### Workflow controls

Implement:
- Start workflow.
- Cancel workflow.
- Retry failed stage.
- Resume supported checkpoints.
- Human approval.
- Workflow history.
- Open output artifact.
- Export execution report.

Implement pause only if backend checkpoint and queue semantics safely support it.

### Real-time architecture

Backend:
FastAPI + LangGraph + event stream + persistent execution records.

Frontend:
React Flow + SSE event subscription + synchronized state.

Persist workflow events with sequence identifiers.

On reconnect, the frontend must recover missed events and rebuild the correct state.

Do not use browser timers to fake agent completion.

---

# 6. SIGNATURE FEATURE TWO
## EVIDENCE-TO-CONTENT TRACEABILITY ENGINE

Build an interactive page named:

**Evidence Intelligence Studio**

The user should be able to inspect every significant factual claim produced by the AI.

### Page layout

Create a three-column interface.

**LEFT — SOURCE LIBRARY**
- Research documents.
- Website references.
- Uploaded PDFs.
- Source credibility metadata.
- Publication dates.
- Extracted passages.
- Source status.

**CENTER — GENERATED CONTENT**
- Rich-text document preview.
- Platform-specific content.
- Highlighted factual claims.
- Inline citation indicators.
- Editing tools.
- Content version history.

**RIGHT — EVIDENCE INSPECTOR**
- Selected claim.
- Verification result.
- Supporting source passages.
- Contradictory evidence.
- Verification explanation.
- Confidence assessment.
- Responsible agent.
- Revision history.

### Interactive claim highlighting

Highlight factual claims based on their verification state.

Supported claim:
Subtle green underline.

Disputed claim:
Red underline.

Unverified claim:
Amber dotted underline.

Non-factual content:
Normal styling.

Example article:

"Electric vehicles produce zero tailpipe emissions."

Clicking the factual claim should display:

Claim:
Electric vehicles produce zero tailpipe emissions.

Status:
Supported.

Evidence:
Relevant source passage and citation.

Important qualification:
This does not mean lifecycle emissions are always zero.

Verification agent:
Fact Checker.

Content version:
Version 2.

### Evidence relationships

Implement a claim-source relationship graph.

Possible relations:
- Supports.
- Contradicts.
- Partially supports.
- Mentions.
- Insufficient evidence.

A claim can connect to multiple sources.

A source can support multiple claims.

### Claim lifecycle

Track:

Generated → Extracted → Evidence Collected → Verified/Disputed/Unverified → Revised → Re-evaluated → Approved.

Every change must be stored.

### Traceability visualization

When a claim is selected:

1. Highlight its location in the document.
2. Highlight connected research sources.
3. Display the evidence relationship.
4. Show the responsible agent.
5. Display the verification explanation.
6. Allow navigation to earlier versions.

Create smooth transitions between views.

### Evidence integrity

Never invent sources or citations.

A claim must not be marked verified merely because an LLM believes it is accurate.

Verification must be based on accessible supporting material.

If sufficient evidence is missing, mark the claim unverified.

Separate source credibility assessment from actual evidentiary support.

Ensure uploaded documents, source passages, URLs, and citations are stored consistently.

---

# 7. MULTI-AGENT SYSTEM DESIGN

Implement at least 10 specialized agents.

### 1. Supervisor Agent
Plans tasks, assigns responsibilities, manages dependencies, and controls execution.

### 2. Research Agent
Collects and extracts relevant source material.

### 3. Strategy Agent
Develops audience, messaging, tone, and content strategy.

### 4. Writer Agent
Creates platform-specific content drafts.

### 5. Fact Checker Agent
Extracts factual claims and evaluates them against evidence.

### 6. Editor Agent
Improves structure, readability, accuracy of expression, and consistency.

### 7. Brand Guardian Agent
Applies reusable brand voice guidelines.

### 8. SEO Agent
Optimizes the content for appropriate channels.

### 9. Quality Agent
Scores content against an explainable rubric and identifies required revisions.

### 10. Export & Publishing Agent
Prepares approved content for export or authorized publication.

Each agent must have:
- A dedicated instruction template.
- Defined input schema.
- Defined output schema.
- Controlled tool access.
- Structured errors.
- Execution records.
- Observable decision summaries.

Implement parallel work where appropriate.

Use shared typed LangGraph state, checkpointing, conditional edges, and explicit termination logic.

Avoid unbounded agent loops.

---

# 8. SMART QUALITY FEEDBACK LOOP

Create a visible automated quality improvement process.

When content receives a low quality score:

1. Identify the failed category.
2. Generate actionable criticism.
3. Route the criticism to the relevant agent.
4. Generate a targeted revision.
5. Re-run applicable verification.
6. Compare revised content.
7. Save both versions.
8. Stop when the threshold or maximum retry count is reached.

Quality dimensions:

- Factual support: 25%.
- Relevance: 20%.
- Clarity: 15%.
- Structure: 15%.
- Brand consistency: 10%.
- Platform suitability: 10%.
- Engagement potential: 5%.

Treat the score as a configurable evaluation heuristic rather than a guarantee.

If factual support cannot be established, preserve the warning regardless of the total numerical score.

---

# 9. COMPLETE WEBSITE PAGES

Build the following connected pages.

## A. Landing Page

Create a visually stunning SaaS landing page.

Include:
- Bold animated headline.
- Interactive hero agent graph.
- Product mockup preview.
- Feature showcase.
- Two flagship innovation sections.
- How-it-works section.
- Professional animations.
- Call to action.

Hero headline:

**One Idea. Ten AI Agents. Infinite Possibilities.**

Subheading:

"Research, create, verify, and refine content with an intelligent team of AI agents working together in real time."

Use a distinctive hero section with an animated multi-agent network.

## B. Main Dashboard

Show:
- Total projects.
- Active agent workflows.
- Generated content count.
- Verified claim coverage.
- Pending approvals.
- Latest executions.
- Agent performance overview.

All meaningful metrics must come from stored workflow data.

## C. Workflow Creation Studio

Include:
- Large AI prompt input.
- File upload.
- URL input.
- Content platform selection.
- Audience controls.
- Tone selection.
- Content goals.
- Brand profile.
- Advanced settings.
- Start Workflow button.

Make the creation experience clean, guided, and responsive.

## D. Agent Control Center

Use the detailed specification from Section 5.

## E. Evidence Intelligence Studio

Use the detailed specification from Section 6.

## F. Content Studio

Include:
- Multi-format output tabs.
- Editable document.
- AI revision requests.
- Side-by-side comparisons.
- Version history.
- Inline comments.
- Export options.

## G. Agent Analytics

Show:
- Agent execution duration.
- Task success rate.
- Retry frequency.
- Model usage.
- Estimated cost.
- Quality history.
- Processing trends.

Use attractive charts with Recharts.

## H. Human Approval Center

Allow reviewers to:
- Inspect generated content.
- View claim warnings.
- Approve drafts.
- Reject drafts.
- Request revisions.
- Record comments.

## I. Publishing Calendar

Create a clean weekly/monthly content calendar.

Support scheduling data and draft management.

Only claim actual publication when a supported integration confirms it.

## J. Settings

Include:
- Model providers.
- API configuration.
- Brand profiles.
- Workflow settings.
- Theme preference.
- Agent settings.
- Export preferences.

---

# 10. ANIMATIONS AND MICRO-INTERACTIONS

Animations are an important part of this project.

Implement:
- Smooth page transitions.
- Responsive hover interactions.
- Animated workflow edges.
- Pulsing active agents.
- Expandable drawers.
- Smooth inspector transitions.
- Real-time status changes.
- Animated metric updates.
- Elegant loading skeletons.
- Sidebar collapse animation.
- Keyboard command palette.
- Polished dialog and toast transitions.

Respect prefers-reduced-motion.

Avoid heavy effects that reduce performance.

Do not sacrifice responsiveness or usability for visual effects.

---

# 11. MOBILE AND RESPONSIVE DESIGN

The desktop experience is the priority for the Agent Control Center.

However, all pages must also work on tablets and mobile devices.

On mobile:
- Convert the left sidebar into a navigation drawer.
- Make the agent graph pannable and zoomable.
- Present the inspector as a bottom sheet or full-screen panel.
- Stack evidence panels intelligently.
- Maintain readable claim highlighting.
- Avoid horizontal overflow.

Test at representative phone, tablet, laptop, and desktop sizes.

---

# 12. DATABASE AND DATA PERSISTENCE

Implement PostgreSQL models for:

- Users.
- Workspaces.
- Projects.
- Content requests.
- Workflow runs.
- Workflow events.
- Agent executions.
- Source documents.
- Source passages.
- Factual claims.
- Claim-evidence links.
- Content artifacts.
- Artifact versions.
- Quality evaluations.
- Review decisions.
- Publishing jobs.
- Usage analytics.

Relationships must enable full traceability from a final content claim back to supporting evidence and generating agent execution.

Use database migrations.

Do not keep important execution history only in frontend memory.

---

# 13. LIVE EXECUTION EVENT SYSTEM

Implement structured backend events such as:

- workflow.created
- workflow.started
- agent.queued
- agent.started
- agent.tool_started
- agent.tool_completed
- agent.output_created
- agent.completed
- agent.failed
- claim.extracted
- claim.verified
- claim.disputed
- claim.unverified
- revision.requested
- revision.completed
- approval.required
- workflow.completed
- workflow.failed

Events must include:
- Event ID.
- Workflow ID.
- Agent ID where applicable.
- Event type.
- Timestamp.
- Safe structured payload.
- Sequence number.

Never store API keys or hidden provider credentials in event payloads.

Use these events to drive the visual execution dashboard.

---

# 14. SECURITY AND RELIABILITY

Implement:
- Authentication.
- Workspace authorization.
- Input validation.
- API key protection.
- Rate limiting.
- Safe file upload handling.
- Prompt injection defenses.
- Tool permission controls.
- Safe external URL fetching.
- Bounded workflow retries.
- Error recovery.
- Consistent transaction handling.
- Logging and audit records.

User-uploaded content and retrieved sources must be treated as untrusted data.

Agent outputs must not be allowed to authorize external publishing, arbitrary code execution, or changes to sensitive settings.

---

# 15. DEMO MODE FOR COLLEGE PRESENTATION

Provide a complete demo mode that runs without paid AI APIs.

Use a realistic example:

"Create a researched content campaign about electric vehicles in India."

Show:
- Supervisor execution.
- Research collection.
- Writer generation.
- Fact-checking.
- A disputed or unverified claim.
- Revision request.
- Updated content.
- Quality evaluation.
- Human approval.
- Evidence-to-content traceability.
- Final content export.

Seed the demonstration with clearly labeled sample inputs, sources, events, and expected outputs.

It should demonstrate the complete product journey, not merely display a static workflow graph.

Do not label demo simulation as live AI execution.

---

# 16. PROJECT TESTING

Test both technical features and visual behavior.

### Agent tests
- Supervisor routing.
- Agent state transitions.
- Parallel execution.
- Failed agent handling.
- Retry termination.
- Re-evaluation.
- Checkpoint recovery.

### Traceability tests
- Claim extraction.
- Evidence linking.
- Evidence status.
- Version tracking.
- Unsupported claims.
- Multiple sources per claim.

### Frontend tests
- Agent graph status updates.
- Inspector interactions.
- Workflow forms.
- Content editing.
- Responsive layouts.
- Evidence claim selection.
- Approval actions.

### End-to-end tests
- Create project.
- Execute workflow.
- Inspect agents.
- Review evidence.
- Revise content.
- Approve content.
- Export final artifact.

Run available tests and report actual outcomes.

---

# 17. DEVELOPMENT ORDER

Execute in the following order.

### Stage 1 — Repository and Architecture
Inspect the existing repository and define the application structure.

### Stage 2 — Premium Design Foundation
Create the design system, navigation, shared components, and responsive layouts.

### Stage 3 — Agent Control Center
Build the graph, nodes, inspector, execution timeline, and event-driven state.

### Stage 4 — Multi-Agent Backend
Implement LangGraph agents, orchestration, execution persistence, and streaming events.

### Stage 5 — Evidence Traceability
Implement source storage, claim extraction, claim-evidence relationships, verification states, and interactive inspection.

### Stage 6 — Content Generation
Connect generated content, version history, editing, and approval workflows.

### Stage 7 — Analytics and Supporting Pages
Complete dashboard analytics, settings, and publishing calendar.

### Stage 8 — Integration and Testing
Verify end-to-end behavior and fix frontend/backend errors.

### Stage 9 — Deployment Readiness
Prepare Docker, environment templates, documentation, and production builds.

Prioritize getting one complete working journey running before expanding every optional feature.

---

# 18. USER EXPERIENCE QUALITY RULES

Every major UI element must have a purpose.

Do not create:
- Empty placeholder dashboards.
- Buttons without handlers.
- Graph nodes that only animate without execution events.
- Invented citations.
- Fake quality scores presented as real.
- Nonfunctional settings.
- Dummy publishing success states.
- Generic AI chat screens as the main interface.
- Hardcoded execution percentages.
- Unhandled error screens.
- Layouts that overlap or break on smaller screens.

Ensure:
- Real backend integration.
- Consistent visual hierarchy.
- Professional spacing.
- Excellent typography.
- Graceful loading and error states.
- Accessible controls.
- Distinct page identities.
- Fast navigation.
- Clear feature discoverability.

---

# 19. REQUIRED DOCUMENTATION

Provide:
- README.md
- ARCHITECTURE.md
- AGENTS.md
- TRACEABILITY.md
- DEPLOYMENT.md
- TESTING.md
- DEMO.md
- VIVA_GUIDE.md

Explain why LangGraph is used, how agents communicate, how live events are produced, how evidence links are stored, and how the project differs from a conventional single-model chatbot.

---

# 20. FINAL PROJECT ACCEPTANCE CRITERIA

The project must demonstrate all of the following:

1. A premium, fully connected frontend.
2. A working FastAPI backend.
3. Database persistence.
4. Real LangGraph orchestration.
5. Interactive React Flow agent visualization.
6. Runtime-driven agent activity updates.
7. Inspectable agent inputs and outputs.
8. Claim extraction.
9. Evidence-source linking.
10. Interactive claim highlighting.
11. Content revision loop.
12. Explainable quality evaluation.
13. Human approval.
14. Multi-platform content generation.
15. Exportable artifacts.
16. Working demonstration mode.
17. Automated tests.
18. Documented deployment configuration.

Do not claim a feature is implemented until its behavior has been verified.

---

# FINAL DIRECTIVE

**BUILD CONTENTFORGE AI AS A PREMIUM MULTI-AGENT CONTENT INTELLIGENCE SYSTEM.**

The two main highlights must be:

**LIVE MULTI-AGENT CONTROL CENTER**
An intelligent visual workspace where users can watch AI agents execute, collaborate, produce outputs, handle feedback, and complete complex workflows.

**EVIDENCE-TO-CONTENT TRACEABILITY ENGINE**
A transparent verification workspace where factual claims can be traced to evidence, source passages, agent decisions, revisions, and final approvals.

Treat visual design, performance, usability, and engineering correctness as equally important.

Aim for the finish quality of a real commercial AI SaaS application rather than a routine academic submission.

Inspect the repository, implement the project, test it, and provide reproducible run/deployment instructions.

If something cannot be implemented or verified, report the limitation explicitly instead of disguising it as completed functionality.

**BEGIN IMPLEMENTATION.**
