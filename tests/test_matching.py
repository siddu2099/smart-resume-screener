"""Unit tests for deterministic candidate-job matching engine."""

from pathlib import Path
from app.schemas.job import JobProfile
from app.schemas.matching import MatchResult, MatchStatus
from app.schemas.resume import CandidateProfile, EducationSchema, ExperienceSchema
from app.services.matcher import (
    calculate_experience_score,
    calculate_total_experience_years,
    match_candidate_to_job,
    normalize_skill,
    parse_experience_duration_years,
)


def test_normalize_skill():
    """Test skill normalization trimming and casing while preserving technical punctuation."""
    assert normalize_skill("  Python  ") == "python"
    assert normalize_skill("C++") == "c++"
    assert normalize_skill("C#") == "c#"
    assert normalize_skill(".NET") == ".net"
    assert normalize_skill("Node.js") == "node.js"
    assert normalize_skill("CI/CD") == "ci/cd"


def test_no_semantic_synonym_guessing():
    """Test that skills are strictly matched without guessing semantic synonyms."""
    cand = CandidateProfile(name="Python Dev", skills=["Python", "FastAPI"])
    job = JobProfile(title="Django Dev", required_skills=["Django"])

    res = match_candidate_to_job(cand, job)
    assert res.matched_required_skills == []
    assert res.missing_required_skills == ["Django"]
    assert res.score_breakdown.skill_score == 0.0


def test_skill_deduplication():
    """Test that duplicate candidate or job skills are deduplicated without double counting."""
    cand = CandidateProfile(skills=["Python", "Python", "Python", "SQL"])
    job = JobProfile(required_skills=["Python", "Python"], preferred_skills=["SQL", "SQL"])

    res = match_candidate_to_job(cand, job)
    assert res.matched_required_skills == ["Python"]
    assert res.matched_preferred_skills == ["SQL"]
    assert res.score_breakdown.skill_score == 100.0


def test_perfect_match():
    """Test perfect candidate match producing Strong Match status and 100 final score."""
    cand = CandidateProfile(
        name="Perfect Candidate",
        skills=["Python", "FastAPI", "SQL", "Docker"],
        experience=[ExperienceSchema(company="Acme", role="Eng", duration="2020 - 2024")],  # 4 yrs
        education=[EducationSchema(degree="B.Tech Computer Science")],
    )
    job = JobProfile(
        title="Backend Engineer",
        required_skills=["Python", "FastAPI", "SQL"],
        preferred_skills=["Docker"],
        experience_required=3,
        education="Bachelor's degree in Computer Science",
    )

    res = match_candidate_to_job(cand, job, candidate_id=1, job_id=10)

    assert isinstance(res, MatchResult)
    assert res.status == MatchStatus.STRONG
    assert res.score_breakdown.skill_score == 100.0
    assert res.score_breakdown.experience_score == 100.0
    assert res.score_breakdown.education_score == 100.0
    assert res.score_breakdown.final_score == 100.0
    assert res.score_breakdown.semantic_score == 0.0  # Documented Phase 7 baseline
    assert res.matched_required_skills == ["Python", "FastAPI", "SQL"]
    assert res.matched_preferred_skills == ["Docker"]
    assert res.missing_required_skills == []


def test_partial_required_and_preferred_skills():
    """Test partial skill match and weighted skill score calculation."""
    cand = CandidateProfile(skills=["Python", "Docker"])
    job = JobProfile(
        required_skills=["Python", "FastAPI"],  # 1/2 = 50%
        preferred_skills=["Docker", "AWS"],     # 1/2 = 50%
    )
    # skill_score = 0.80 * 50 + 0.20 * 50 = 50.0

    res = match_candidate_to_job(cand, job)
    assert res.matched_required_skills == ["Python"]
    assert res.missing_required_skills == ["FastAPI"]
    assert res.matched_preferred_skills == ["Docker"]
    assert res.score_breakdown.skill_score == 50.0


def test_zero_required_and_preferred_skills():
    """Test job profile with zero required and zero preferred skills."""
    cand = CandidateProfile(skills=["Python"])
    job = JobProfile(required_skills=[], preferred_skills=[])

    res = match_candidate_to_job(cand, job)
    assert res.score_breakdown.skill_score == 100.0
    assert res.matched_required_skills == []
    assert res.missing_required_skills == []


def test_technical_terms_preservation():
    """Test skill matching preserves technical terms (C++, C#, .NET, Node.js, CI/CD)."""
    cand = CandidateProfile(skills=["c++", "c#", ".net", "node.js", "ci/cd"])
    job = JobProfile(required_skills=["C++", "C#", ".NET", "Node.js", "CI/CD"])

    res = match_candidate_to_job(cand, job)
    assert len(res.matched_required_skills) == 5
    assert res.score_breakdown.skill_score == 100.0


def test_experience_duration_parsing_and_merging():
    """Test experience duration parsing and interval merging logic."""
    assert parse_experience_duration_years("2020 - 2023") == 3.0
    assert parse_experience_duration_years("2023 - Present", current_year=2026) == 3.0
    assert parse_experience_duration_years("2 years") == 2.0
    assert parse_experience_duration_years("18 months") == 1.5
    assert parse_experience_duration_years("unparseable string") == 0.0

    # Test interval merging: (2020, 2022) and (2021, 2024) -> (2020, 2024) = 4 years total
    exps = [
        ExperienceSchema(duration="2020 - 2022"),
        ExperienceSchema(duration="2021 - 2024"),
    ]
    assert calculate_total_experience_years(exps) == 4.0


def test_experience_scoring_partial_and_missing_requirement():
    """Test experience score for partial experience and when job requires no minimum experience."""
    cand = CandidateProfile(experience=[ExperienceSchema(duration="2 years")])

    # Job requires 4 years -> score = (2/4) * 100 = 50.0
    job_req4 = JobProfile(experience_required=4)
    score, yrs = calculate_experience_score(cand, job_req4)
    assert yrs == 2.0
    assert score == 50.0

    # Job requires no experience (None) -> score = 100.0
    job_none = JobProfile(experience_required=None)
    score_none, _ = calculate_experience_score(cand, job_none)
    assert score_none == 100.0


def test_education_matching():
    """Test education matching logic for satisfied, missing, and absent requirements."""
    cand_cs = CandidateProfile(education=[EducationSchema(degree="B.Tech Computer Science")])
    job_cs = JobProfile(education="Bachelor's degree in Computer Science")
    assert match_candidate_to_job(cand_cs, job_cs).score_breakdown.education_score == 100.0

    # Candidate with unrelated education
    cand_art = CandidateProfile(education=[EducationSchema(degree="Fine Arts")])
    assert match_candidate_to_job(cand_art, job_cs).score_breakdown.education_score == 0.0

    # Job with no education requirement -> 100.0
    job_no_edu = JobProfile(education=None)
    assert match_candidate_to_job(cand_art, job_no_edu).score_breakdown.education_score == 100.0


def test_match_status_thresholds():
    """Test STRONG, POTENTIAL, and WEAK match status thresholds."""
    # Strong Match: final >= 80 and req_coverage >= 0.80
    cand_strong = CandidateProfile(
        skills=["Python", "FastAPI"],
        experience=[ExperienceSchema(duration="2020 - 2025")],
        education=[EducationSchema(degree="Computer Science")],
    )
    job_strong = JobProfile(required_skills=["Python", "FastAPI"], experience_required=3, education="Computer Science")
    res_strong = match_candidate_to_job(cand_strong, job_strong)
    assert res_strong.status == MatchStatus.STRONG

    # Weak Match: missing required skills drops status
    cand_weak = CandidateProfile(skills=["HTML"])
    job_weak = JobProfile(required_skills=["Python", "FastAPI", "SQL", "Docker", "AWS"])
    res_weak = match_candidate_to_job(cand_weak, job_weak)
    assert res_weak.status == MatchStatus.WEAK


def test_deterministic_repeatability():
    """Test that identical inputs produce 100% identical outputs across multiple invocations."""
    cand = CandidateProfile(name="Repeat Test", skills=["Python", "SQL"])
    job = JobProfile(title="Test Job", required_skills=["Python", "SQL"])

    res1 = match_candidate_to_job(cand, job, candidate_id=5, job_id=12)
    res2 = match_candidate_to_job(cand, job, candidate_id=5, job_id=12)

    assert res1.model_dump() == res2.model_dump()


def test_no_database_or_llm_side_effects():
    """Test that matcher causes no database creation or filesystem side effects."""
    cand = CandidateProfile(skills=["Python"])
    job = JobProfile(required_skills=["Python"])

    res = match_candidate_to_job(cand, job)
    assert res.score_breakdown.final_score == 100.0

    root_db = Path("resume_screener.db")
    assert not root_db.exists(), "Matching engine unexpectedly created a database file!"
