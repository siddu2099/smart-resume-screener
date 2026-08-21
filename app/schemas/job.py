"""Pydantic v2 schemas for job description structured data contracts."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class JobProfile(BaseModel):
    """Structured job description schema extracted from job posting text.

    Note: Pydantic validates structural integrity and types of job description data,
    not factual truth or accuracy of LLM outputs.
    """

    title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: Optional[float] = Field(default=None, ge=0.0, le=50.0)
    education: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    """API request schema for creating a job posting."""

    description: str = Field(..., min_length=1, description="Raw job description text")


class JobResponse(BaseModel):
    """API response schema for created or retrieved job posting."""

    job_id: int
    title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: Optional[float] = None
    education: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
    description: str
    created_at: Optional[datetime] = None
