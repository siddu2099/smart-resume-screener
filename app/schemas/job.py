"""Pydantic v2 schemas for job posting structured data contracts."""

from typing import Optional, Union
from pydantic import BaseModel, Field


class JobProfile(BaseModel):
    """Structured job description profile schema.

    Note: Required and preferred skills are strictly kept separate for
    downstream matching engines.
    """

    title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: Optional[Union[float, int, str]] = None
    education: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
