from pydantic import BaseModel, Field


class ExplanationPart(BaseModel):
    text: str
    url: str | None = None
    emphasis: bool = False


class ExampleSource(BaseModel):
    title: str
    publisher: str
    category: str
    takeaway: str
    url: str
    site: str


class ExampleResult(BaseModel):
    claim: str
    verdict: str
    tag: str
    confidence: int = Field(ge=0, le=100)
    explanation: list[ExplanationPart]
    sources: list[ExampleSource]
    relatedClaims: list[str]
