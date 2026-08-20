"""Unit tests for Pydantic v2 domain schemas."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas import (
    CandidateProfile,
    EducationSchema,
    ExperienceSchema,
    JobProfile,
    MatchResult,
    MatchStatus,
    ScoreBreakdown,
    SemanticMatchResult,
    ShortlistCandidate,
    ShortlistResult,
)


# --- CandidateProfile Tests (1-5) ---


def test_candidate_profile_complete():
    """1. Test creating a complete valid candidate profile."""
    exp = ExperienceSchema(company="Acme", role="Engineer", duration="2 years", description="Python dev")
    edu = EducationSchema(degree="B.S.", institution="State Uni", year="2022")
    candidate = CandidateProfile(
        name="Jane Doe",
        email="jane@example.com",
        phone="+1234567890",
        skills=["Python", "FastAPI"],
        experience=[exp],
        education=[edu],
    )
    assert candidate.name == "Jane Doe"
    assert candidate.skills == ["Python", "FastAPI"]
    assert candidate.experience[0].company == "Acme"
    assert candidate.education[0].year == "2022"


def test_candidate_profile_name_and_skills_only():
    """2. Test candidate profile with only name and skills."""
    candidate = CandidateProfile(name="John Smith", skills=["SQL", "Docker"])
    assert candidate.name == "John Smith"
    assert candidate.skills == ["SQL", "Docker"]
    assert candidate.email is None
    assert candidate.experience == []


def test_candidate_profile_missing_optional_fields():
    """3. Test candidate profile with all optional fields omitted."""
    candidate = CandidateProfile()
    assert candidate.name is None
    assert candidate.email is None
    assert candidate.phone is None
    assert candidate.skills == []
    assert candidate.experience == []
    assert candidate.education == []


def test_candidate_profile_empty_lists():
    """4. Test candidate profile explicitly initialized with empty lists."""
    candidate = CandidateProfile(skills=[], experience=[], education=[])
    assert candidate.skills == []
    assert candidate.experience == []
    assert candidate.education == []


def test_candidate_profile_invalid_list_type():
    """5. Test candidate profile failing on invalid list type."""
    with pytest.raises(ValidationError):
        CandidateProfile(skills="not-a-list")


# --- ExperienceSchema Tests (6-7) ---


def test_experience_schema_valid():
    """6. Test valid experience entry."""
    exp = ExperienceSchema(company="Tech Corp", role="Senior Engineer", duration="2020-2023", description="Led backend team")
    assert exp.company == "Tech Corp"
    assert exp.duration == "2020-2023"


def test_experience_schema_missing_optionals():
    """7. Test experience entry with missing optional fields."""
    exp = ExperienceSchema()
    assert exp.company is None
    assert exp.role is None


# --- EducationSchema Tests (8-9) ---


def test_education_schema_valid():
    """8. Test valid education entry."""
    edu = EducationSchema(degree="M.S. CS", institution="MIT", year="2023")
    assert edu.degree == "M.S. CS"
    assert edu.year == "2023"


def test_education_schema_missing_year():
    """9. Test education entry with missing year."""
    edu = EducationSchema(degree="B.S. Mathematics", institution="Harvard")
    assert edu.year is None


# --- JobProfile Tests (10-13) ---


def test_job_profile_complete():
    """10. Test complete job profile."""
    job = JobProfile(
        title="Backend Engineer",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker", "AWS"],
        experience_required=3,
        education="B.S. Computer Science",
        responsibilities=["Build REST APIs", "Optimize queries"],
    )
    assert job.title == "Backend Engineer"
    assert job.required_skills == ["Python", "FastAPI"]
    assert job.preferred_skills == ["Docker", "AWS"]
    assert job.experience_required == 3


def test_job_profile_without_experience_requirement():
    """11. Test job profile without experience requirement."""
    job = JobProfile(title="Junior Dev", required_skills=["Python"])
    assert job.experience_required is None


def test_job_profile_without_education_requirement():
    """12. Test job profile without education requirement."""
    job = JobProfile(title="Self-taught Developer", required_skills=["Java"])
    assert job.education is None


def test_job_profile_separate_skills():
    """13. Test that required and preferred skills remain separate."""
    job = JobProfile(
        required_skills=["Python"],
        preferred_skills=["Kubernetes"],
    )
    assert job.required_skills != job.preferred_skills
    assert "Python" in job.required_skills
    assert "Kubernetes" in job.preferred_skills


# --- SemanticMatchResult & ScoreBreakdown Tests (14-20) ---


def test_semantic_match_result_min_max_scores():
    """14-15. Test SemanticMatchResult with minimum (0) and maximum (100) scores."""
    res_min = SemanticMatchResult(semantic_score=0.0)
    res_max = SemanticMatchResult(semantic_score=100.0)
    assert res_min.semantic_score == 0.0
    assert res_max.semantic_score == 100.0


def test_semantic_match_result_invalid_scores():
    """16-17. Test SemanticMatchResult failing when score < 0 or > 100."""
    with pytest.raises(ValidationError):
        SemanticMatchResult(semantic_score=-0.1)

    with pytest.raises(ValidationError):
        SemanticMatchResult(semantic_score=100.1)


def test_semantic_match_result_defaults():
    """18. Test SemanticMatchResult default list values."""
    res = SemanticMatchResult(semantic_score=85.0)
    assert res.strengths == []
    assert res.gaps == []
    assert res.justification == ""


def test_score_breakdown_valid():
    """19. Test valid ScoreBreakdown."""
    sb = ScoreBreakdown(
        skill_score=90.0,
        experience_score=80.0,
        education_score=85.0,
        semantic_score=88.0,
        final_score=86.5,
    )
    assert sb.final_score == 86.5


def test_score_breakdown_invalid_range():
    """20. Test ScoreBreakdown rejecting out-of-range scores."""
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            skill_score=105.0,
            experience_score=80.0,
            education_score=85.0,
            semantic_score=88.0,
            final_score=86.5,
        )


# --- MatchResult & MatchStatus Tests (21-24) ---


def test_match_result_valid_nested():
    """21. Test valid nested MatchResult."""
    sb = ScoreBreakdown(
        skill_score=90.0,
        experience_score=80.0,
        education_score=85.0,
        semantic_score=88.0,
        final_score=86.5,
    )
    match = MatchResult(
        candidate_id=1,
        job_id=10,
        score_breakdown=sb,
        status=MatchStatus.STRONG,
        matched_required_skills=["Python"],
    )
    assert match.candidate_id == 1
    assert match.status == MatchStatus.STRONG
    assert match.score_breakdown.skill_score == 90.0


def test_match_result_invalid_nested_score():
    """22. Test MatchResult failing when nested score is invalid."""
    with pytest.raises(ValidationError):
        MatchResult(
            candidate_id=1,
            job_id=10,
            score_breakdown={"skill_score": -5.0, "experience_score": 80, "education_score": 80, "semantic_score": 80, "final_score": 80},
            status=MatchStatus.STRONG,
        )


def test_match_status_enum():
    """23-24. Test MatchStatus enum valid and invalid values."""
    assert MatchStatus.STRONG == "Strong Match"
    assert MatchStatus.POTENTIAL == "Potential Match"
    assert MatchStatus.WEAK == "Weak Match"

    with pytest.raises(ValidationError):
        MatchResult(
            candidate_id=1,
            job_id=10,
            score_breakdown=ScoreBreakdown(skill_score=50, experience_score=50, education_score=50, semantic_score=50, final_score=50),
            status="Invalid Status String",
        )


# --- ShortlistResult Tests (25-26) ---


def test_shortlist_result_multiple_candidates():
    """25. Test ShortlistResult with multiple candidates."""
    c1 = ShortlistCandidate(candidate_id=1, candidate_name="Alice", final_score=95.0, status=MatchStatus.STRONG)
    c2 = ShortlistCandidate(candidate_id=2, candidate_name="Bob", final_score=75.0, status=MatchStatus.POTENTIAL)
    shortlist = ShortlistResult(job_id=100, candidates=[c1, c2])

    assert shortlist.job_id == 100
    assert len(shortlist.candidates) == 2
    assert shortlist.candidates[0].candidate_name == "Alice"


def test_shortlist_result_empty_candidates():
    """26. Test ShortlistResult with default empty candidate list."""
    shortlist = ShortlistResult(job_id=101)
    assert shortlist.candidates == []


# --- Default Factory & Import Side Effects Tests (27-28) ---


def test_default_factory_independence():
    """27. Test that default_factory list instances are independent across objects."""
    c1 = CandidateProfile(name="C1")
    c2 = CandidateProfile(name="C2")

    c1.skills.append("Python")
    assert "Python" in c1.skills
    assert "Python" not in c2.skills


def test_schema_import_no_side_effects():
    """28. Test that schema imports create no database files or root side effects."""
    root_db = Path("resume_screener.db")
    assert not root_db.exists(), "Schema import unexpectedly created database file!"
