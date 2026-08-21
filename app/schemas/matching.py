"""Pydantic v2 schemas for candidate-job matching, scoring, and shortlist contracts."""

from enum import Enum
from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    """Candidate match qualification status."""

    STRONG = "Strong Match"
    POTENTIAL = "Potential Match"
    WEAK = "Weak Match"


class SemanticMatchResult(BaseModel):
    """LLM semantic match evaluation result schema."""

    semantic_score: float = Field(ge=0.0, le=100.0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    justification: str = ""


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown across individual candidate evaluation dimensions."""

    skill_score: float = Field(ge=0.0, le=100.0)
    experience_score: float = Field(ge=0.0, le=100.0)
    education_score: float = Field(ge=0.0, le=100.0)
    semantic_score: float = Field(ge=0.0, le=100.0)
    final_score: float = Field(ge=0.0, le=100.0)


class MatchRequest(BaseModel):
    """API request schema for candidate-job matching evaluation."""

    candidate_id: int
    job_id: int


class MatchResult(BaseModel):
    """Complete candidate-job match result schema."""

    candidate_id: int
    job_id: int
    score_breakdown: ScoreBreakdown
    status: MatchStatus
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    justification: str = ""


class ShortlistCandidate(BaseModel):
    """Candidate entry in job shortlist results."""

    candidate_id: int
    candidate_name: str
    final_score: float = Field(ge=0.0, le=100.0)
    status: MatchStatus
    justification: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ShortlistResult(BaseModel):
    """Ranked candidate shortlist result for a job posting."""

    job_id: int
    candidates: list[ShortlistCandidate] = Field(default_factory=list)
