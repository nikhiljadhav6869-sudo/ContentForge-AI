from typing import Literal
from pydantic import BaseModel, Field, field_validator

Platform = Literal["blog", "linkedin", "instagram", "youtube"]


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default="Creator", min_length=1, max_length=80)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)


class Brief(BaseModel):
    project_id: str | None = None
    prompt: str = Field(min_length=10, max_length=4000)
    audience: str = Field(default="Indian college students", max_length=200)
    tone: str = Field(default="Clear and educational", max_length=100)
    goals: str = Field(default="Educate and inspire informed action", max_length=1000)
    brand: str = Field(default="Helpful, evidence-led, inclusive. Avoid hype.", max_length=2000)
    platforms: list[Platform] = Field(default=["blog", "linkedin", "instagram", "youtube"], min_length=1, max_length=4)
    mode: Literal["demo", "openai", "gemini", "ollama"] = "demo"
    source_ids: list[str] = Field(default=[], max_length=12)
    max_revisions: int = Field(default=1, ge=0, le=2)
    quality_threshold: int = Field(default=80, ge=50, le=100)

    @field_validator("platforms", "source_ids")
    @classmethod
    def unique(cls, values):
        return list(dict.fromkeys(values))


class TextSource(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=20, max_length=100000)


class URLSource(BaseModel):
    url: str = Field(max_length=2000)


class ReviewInput(BaseModel):
    decision: Literal["approve", "reject", "revise"]
    comment: str = Field(default="", max_length=2000)
    acknowledge_warnings: bool = False


class EditInput(BaseModel):
    body: str = Field(min_length=10, max_length=40000)
    base_version: int = Field(ge=1)


class CommentInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    quote: str = Field(default="", max_length=500)


class ScheduleInput(BaseModel):
    artifact_id: str
    scheduled_at: str


class Preferences(BaseModel):
    brand_name: str = Field(default="My brand", max_length=100)
    brand_voice: str = Field(default="Helpful, evidence-led, inclusive. Avoid hype.", max_length=2000)
    default_provider: Literal["demo", "openai", "gemini", "ollama"] = "demo"
    theme: Literal["dark", "light", "system"] = "dark"
    export_format: Literal["markdown", "json"] = "markdown"
    quality_threshold: int = Field(default=80, ge=50, le=100)
    max_revisions: int = Field(default=1, ge=0, le=2)


class AgentInput(BaseModel):
    brief: dict
    context: dict
    instruction: str


class AgentOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    data: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class EvidenceInput(BaseModel):
    passage_id: str
    relation: Literal["supports", "contradicts", "partially_supports", "mentions", "insufficient_evidence"]
    quote: str = Field(min_length=10, max_length=1200)
    explanation: str = Field(min_length=10, max_length=2000)


class SupervisorData(BaseModel):
    plan: list[str]
    routing: str


class ResearchData(BaseModel):
    findings: list[str]
    source_ids: list[str]
    gaps: list[str]


class StrategyData(BaseModel):
    angle: str
    outline: list[str]
    audience: str
    tone: str


class DraftData(BaseModel):
    platform: Platform
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=20, max_length=40000)


class WriterData(BaseModel):
    artifacts: list[DraftData] = Field(min_length=1, max_length=4)


class EditorData(BaseModel):
    notes: list[str]
    revised_artifacts: list[DraftData] = Field(min_length=1, max_length=4)


class BrandData(EditorData):
    pass


class SEOData(BaseModel):
    metadata: dict
    revised_artifacts: list[DraftData] = Field(min_length=1, max_length=4)


class QualityData(BaseModel):
    criticism: list[str]
    recommended_agent: str


AGENT_DATA_SCHEMAS = {
    "supervisor": SupervisorData,
    "research": ResearchData,
    "strategy": StrategyData,
    "writer": WriterData,
    "editor": EditorData,
    "brand": BrandData,
    "seo": SEOData,
    "quality": QualityData,
}
