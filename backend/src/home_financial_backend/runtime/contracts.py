from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClassificationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    source: Literal["llm_fallback"]
    review_required: bool
