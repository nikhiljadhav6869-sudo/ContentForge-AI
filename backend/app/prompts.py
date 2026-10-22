AGENTS = {
    "supervisor": (
        "Supervisor",
        "Turn the brief into a bounded execution plan with research, strategy, writing, verification, editing, brand, SEO, quality, human approval, and export. data: {plan: string[], routing: string}.",
    ),
    "research": (
        "Research",
        "Summarize only the provided source passages. Do not browse, invent sources, or claim verification. Identify gaps. data: {findings: string[], source_ids: string[], gaps: string[]}.",
    ),
    "strategy": (
        "Strategy",
        "Plan the requested content campaign for its audience, goals, formats, and brand. data: {angle: string, outline: string[], audience: string, tone: string}.",
    ),
    "writer": (
        "Writer",
        "Write complete content for every requested platform. Use only supplied references for factual claims. Quote important evidence sentences exactly so they can be traced. On revision remove unsupported claims and address feedback. data: {artifacts: [{platform: string, title: string, body: string}]}. Platforms must match the brief. Use plain text with Markdown headings.",
    ),
    "fact_checker": (
        "Fact Checker",
        "Extract factual claims and suggest evidence comparisons; deterministic evidence checks govern final status. data: {claims: [{text: string, passage_id: string, quote: string}], concerns: string[]}.",
    ),
    "editor": (
        "Editor",
        "Inspect the drafts for readability, structure, and accuracy of expression. Return actionable edit notes without adding claims. data: {notes: string[], revised_artifacts: [{platform: string, title: string, body: string}]}. Include complete edited artifacts for each platform.",
    ),
    "brand": (
        "Brand Guardian",
        "Apply the user brand voice and tone; inspect the drafts and return complete revised artifacts. Preserve citations and avoid new facts. data: {notes: string[], revised_artifacts: [{platform: string, title: string, body: string}]}.",
    ),
    "seo": (
        "SEO & Channels",
        "Adapt each draft to its requested channel with a headline, metadata, and suitable call to action. Preserve factual statements and do not add statistics. data: {metadata: object, revised_artifacts: [{platform: string, title: string, body: string}]}.",
    ),
    "quality": (
        "Quality",
        "Evaluate the supplied content and evidence findings. Suggest targeted revisions. Never override evidence warnings with a score. data: {criticism: string[], recommended_agent: string}.",
    ),
    "export": (
        "Export & Publishing",
        "Package only the exact human-approved versions for download. External publishing is not enabled.",
    ),
}
