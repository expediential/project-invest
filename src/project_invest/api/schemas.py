from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchRunRequest(BaseModel):
    symbols: list[str] | None = None


class ResearchJobRequest(BaseModel):
    symbols: list[str] | None = None
    purpose: str = Field(default="On-demand research cycle", max_length=240)

