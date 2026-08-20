"""Pydantic v2 schemas for candidate/resume structured data contracts."""

from typing import Optional
from pydantic import BaseModel, Field


class ExperienceSchema(BaseModel):
    """Work experience entry schema."""

    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class EducationSchema(BaseModel):
    """Education history entry schema."""

    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None


class CandidateProfile(BaseModel):
    """Structured candidate profile schema extracted from resume text.

    Note: Pydantic validates structural integrity and types of candidate data,
    not factual truth or accuracy of LLM outputs.
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceSchema] = Field(default_factory=list)
    education: list[EducationSchema] = Field(default_factory=list)
