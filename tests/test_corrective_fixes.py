"""Regression tests verifying deterministic facts override LLM semantic explanations."""

import json
from unittest.mock import MagicMock

import pytest

from app.schemas.job import JobProfile
from app.schemas.matching import MatchResult, MatchStatus, SemanticMatchResult
from app.schemas.resume import CandidateProfile
from app.services.matcher import match_candidate_to_job
from app.services.semantic_matcher import (
    evaluate_semantic_match,
    sanitize_semantic_explanation,
    sanitize_semantic_result,
)


def test_required_skill_described_as_preferred_sanitized():
    """Test 1: LLM incorrectly calling a required skill 'preferred' is sanitized to 'required'."""
    job = JobProfile(
        title="Data Engineer",
        required_skills=["Python", "SQL", "Teradata", ".NET"],
        preferred_skills=["Docker"],
        education="B.Tech in CS",
    )
    raw_justification = "The candidate is missing Teradata, which is a preferred skill."
    sanitized = sanitize_semantic_explanation(
        raw_justification,
        required_skills=job.required_skills,
        missing_skills=["Teradata"],
        has_education=True,
    )
    assert "preferred skill" not in sanitized.lower()
    assert "required skill" in sanitized.lower()


def test_missing_required_skill_not_claimed_as_matched():
    """Test 2: LLM claiming a missing required skill is matched/possessed is filtered from strengths."""
    job = JobProfile(
        title="Backend Developer",
        required_skills=["Java", "Oracle", "Teradata"],
        preferred_skills=[],
    )
    cand = CandidateProfile(
        name="Alice",
        skills=["Java"],
    )
    sem_result = SemanticMatchResult(
        semantic_score=80.0,
        strengths=["Has Java", "Proficient in Oracle", "Good teamwork"],
        gaps=["Missing Teradata"],
        justification="Strong candidate",
    )
    result = match_candidate_to_job(cand, job, semantic_result=sem_result)
    assert "Proficient in Oracle" not in result.strengths
    assert "Missing required skills: Oracle, Teradata" in result.gaps[0]
    assert "Oracle" in result.missing_required_skills
    assert "Teradata" in result.missing_required_skills


def test_required_and_preferred_classification_is_deterministic():
    """Test 3: Required and preferred skill classification remains strictly deterministic."""
    job = JobProfile(
        title="Full Stack Dev",
        required_skills=["React", "Node.js"],
        preferred_skills=["GraphQL"],
    )
    cand = CandidateProfile(name="Bob", skills=["React", "GraphQL"])
    result = match_candidate_to_job(cand, job)
    assert result.matched_required_skills == ["React"]
    assert result.missing_required_skills == ["Node.js"]
    assert result.matched_preferred_skills == ["GraphQL"]


def test_required_skill_coverage_remains_authoritative():
    """Test 4: Required skill coverage remains deterministic (1 / 2 = 50%)."""
    job = JobProfile(
        title="DevOps",
        required_skills=["Docker", "Kubernetes"],
    )
    cand = CandidateProfile(name="Charlie", skills=["Docker"])
    result = match_candidate_to_job(cand, job)
    assert len(result.matched_required_skills) == 1
    assert len(result.missing_required_skills) == 1


def test_existing_education_requirement_not_described_as_absent():
    """Test 5: When job.education exists, 'No explicit education requirement specified' is stripped."""
    job = JobProfile(
        title="Consulting Analyst",
        required_skills=["Java"],
        education="BE - B.Tech / IT, Computer Science or Circuit branches",
    )
    cand = CandidateProfile(
        name="Dave",
        skills=["Java"],
        education=[{"degree": "B.Tech in Computer Science"}],
    )
    sem_result = SemanticMatchResult(
        semantic_score=85.0,
        strengths=["No explicit education requirement specified", "Solid tech skills"],
        gaps=[],
        justification="Good fit. No explicit education requirement specified.",
    )
    result = match_candidate_to_job(cand, job, semantic_result=sem_result)
    assert "No explicit education requirement specified" not in result.strengths
    assert "no explicit education requirement" not in result.justification.lower()
    assert "Satisfies education requirement" in result.strengths


def test_job_with_no_education_requirement_allows_statement():
    """Test 6: Job with no education requirement still produces 'No explicit education requirement specified'."""
    job = JobProfile(
        title="Developer",
        required_skills=["Python"],
        education=None,
    )
    cand = CandidateProfile(name="Eve", skills=["Python"])
    result = match_candidate_to_job(cand, job)
    assert "No explicit education requirement specified" in result.strengths


def test_final_score_formula_unchanged_by_sanitization():
    """Test 7: Final score formula remains exactly 50% skill + 25% exp + 10% edu + 15% semantic."""
    job = JobProfile(
        title="Tester",
        required_skills=["Selenium"],
        experience_required=2,
        education="B.S.",
    )
    cand = CandidateProfile(
        name="Frank",
        skills=["Selenium"],
        experience=[{"company": "A", "role": "QA", "duration": "2024 - 2026"}],
        education=[{"degree": "B.S."}],
    )
    sem_result = SemanticMatchResult(
        semantic_score=80.0,
        strengths=["Selenium, which is a preferred skill"],
        justification="Tested candidate.",
    )
    result = match_candidate_to_job(cand, job, semantic_result=sem_result)
    assert result.score_breakdown.skill_score == 100.0
    assert result.score_breakdown.experience_score == 100.0
    assert result.score_breakdown.education_score == 100.0
    assert result.score_breakdown.semantic_score == 80.0
    assert result.score_breakdown.final_score == 97.0


def test_match_status_thresholds_deterministic():
    """Test 8: MatchStatus remains deterministic based on final_score and required_skill_coverage."""
    job = JobProfile(
        title="Senior Lead",
        required_skills=["Python", "Java", "C++", "SQL", "AWS"],
    )
    cand = CandidateProfile(
        name="Grace",
        skills=["Python"],
    )
    sem_result = SemanticMatchResult(
        semantic_score=100.0,
        justification="Amazing semantic fit!",
    )
    result = match_candidate_to_job(cand, job, semantic_result=sem_result)
    assert result.status == MatchStatus.WEAK
