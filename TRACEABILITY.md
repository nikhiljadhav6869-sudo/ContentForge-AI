# Evidence-to-content traceability

## The data chain

`Workspace → Project → WorkflowRun → AgentExecution → ContentArtifact → ArtifactVersion → FactualClaim → ClaimEvidence → SourcePassage → SourceDocument`

A source stores the exact extracted text, source type, URL if applicable, publication date if supplied, provenance/credibility note, ingestion time, and SHA-256. Passages are bounded chunks of the stored text. URLs are never invented to make a citation look credible.

Claims have an immutable version ID, exact character offsets, text, responsible execution, status, explanation, and lifecycle history. Selecting a claim highlights its span, connected documents, relationship branches, and quoted passages. Earlier versions retain their own claims and evidence.

## What the statuses mean

- **Supported:** the claim is quoted verbatim in an accessible stored passage, or a human has assessed a linked exact quote as supporting it. This is textual evidentiary support, not independently verified truth.
- **Disputed:** contradictory evidence is linked. The demo uses an explicit, labeled contradiction fixture; humans can record additional contradictions.
- **Unverified:** insufficient evidence, partial support, mere mention, or a new human edit awaiting assessment. Lack of support does not establish falsehood.

Relations support `supports`, `contradicts`, `partially_supports`, `mentions`, and `insufficient_evidence`. Multiple passages can support one claim; one passage can be linked to many claims. Human assessments require an exact stored quote and written explanation. They are restricted to the campaign’s current version while awaiting approval and are audited with the reviewer ID. Existing contradictory evidence takes precedence over added supporting links.

## Extraction and validation

The initial extractor is a transparent sentence heuristic, not an exhaustive semantic fact detector. It identifies sufficiently long declarative sentences and excludes common questions and imperative prompts. It can miss factual fragments and over-extract subjective statements. All matching spans are checked against the original version text. Automatic support uses conservative verbatim matches; it does not accept an LLM confidence label. Semantic matching, corpus-wide contradiction search, OCR, and external fact-checking integrations remain future work.

Live agents see supplied sources as untrusted reference data. References cannot authorize tools, credentials, publication, or configuration changes. Fact-checking and export use deterministic tools even when the writing stages use live models.

## Version and approval rules

The lifecycle records generated, extracted, evidence-collected, status, re-evaluation, and human approval events. Writer/editor/brand/channel modifications create versions only when the body changes. Quality rechecks final text after all modifying agents. Human edits create a new version and set extracted claims unverified rather than inheriting older links.

A review pins exact current version IDs. Approving warnings does not convert them to supported claims. Export verifies the approval-version set again. Editorial schedules reference an approved version, and newer versions flag any existing schedule as needing review.

ZIP exports package only those approved versions. Their evidence file includes current-version claims, linked passages, and source metadata, preserving warnings and demo labels. Unlinked passages, earlier drafts, and execution logs are excluded. A manifest maps file hashes and artifact/version IDs for inspection outside the app; it is not a digital signature. See [EXPORTS.md](EXPORTS.md).

## Demonstration evidence

The EV demonstration seeds two local sample reference documents. It deliberately includes an unsupported range statement and a lifecycle-emission overclaim in the first draft. The quality loop requests a revision, removes those statements, retains the original version and evidence, and asks for human approval. Sample source agreement must not be presented as independent research or an official citation.

## Formatting and Unicode offsets

Rich-text versions store supported formatting separately from canonical `body` text. Paragraphs are flattened in document order with two newline characters between them; hard line breaks contribute one newline. The API requires the document and body to match. Claims and comments refer to this canonical text, and formatting-only saves still create a new version requiring evidence review. Evidence highlights use Unicode code-point offsets to match Python extraction, including when emoji precede a claim.
