"""Retrieval-only contract: deliberately contains no assessment fields."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NormalizedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    intervention: str
    outcome: str
    population: str | None = None
    relation: str
    negated: bool
    version: Literal["rules-v1", "foundry-v1"] = "rules-v1"
