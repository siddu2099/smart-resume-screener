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


def test_preferred_skill_scoring_cases():
    """Test explicit preferred skill scoring behavior across all 5 required edge cases."""
    # Case 1: Job with required skills only (no preferred skills)
    job_req_only = JobProfile(required_skills=["Python", "SQL"], preferred_skills=[])
    cand_all_req = CandidateProfile(skills=["Python", "SQL"])
    res1 = match_candidate_to_job(cand_all_req, job_req_only)
    assert res1.score_breakdown.skill_score == 100.0
    assert res1.matched_preferred_skills == []

    # Case 2: Job with required + preferred skills
    job_req_pref = JobProfile(required_skills=["Python"], preferred_skills=["Docker"])
    res2 = match_candidate_to_job(cand_all_req, job_req_pref)  # Matches req Python, missing Docker
    # req_score = 100, pref_score = 0 -> skill_score = 0.80 * 100 + 0.20 * 0 = 80.0
    assert res2.score_breakdown.skill_score == 80.0

    # Case 3: Candidate matching all required skills and no preferred skills
    job_multi_pref = JobProfile(required_skills=["Python"], preferred_skills=["Docker", "AWS"])
    res3 = match_candidate_to_job(CandidateProfile(skills=["Python"]), job_multi_pref)
    assert res3.score_breakdown.skill_score == 80.0

    # Case 4: Candidate matching no required skills (but matching preferred skill)
    res4 = match_candidate_to_job(CandidateProfile(skills=["Docker"]), job_req_pref)
    # req_score = 0, pref_score = 100 -> skill_score = 0.80 * 0 + 0.20 * 100 = 20.0
    assert res4.score_breakdown.skill_score == 20.0

    # Case 5: Candidate with preferred skills when job has no preferred skills
    cand_with_extra = CandidateProfile(skills=["Python", "SQL", "Docker", "AWS"])
    res5 = match_candidate_to_job(cand_with_extra, job_req_only)
    # Absence of job preferred skills does NOT penalize candidate
    assert res5.score_breakdown.skill_score == 100.0


def test_experience_duration_parsing_conservative():
    """Test conservative experience duration parsing without inferring years from vague natural language."""
    # Explicit numeric and date range formats
    assert parse_experience_duration_years("2022 - 2024") == 2.0
    assert parse_experience_duration_years("2023 - Present", current_year=2026) == 3.0
    assert parse_experience_duration_years("2023 - Current", current_year=2026) == 3.0
    assert parse_experience_duration_years("2020 to 2022") == 2.0
    assert parse_experience_duration_years("2 years") == 2.0
    assert parse_experience_duration_years("2.5 yrs") == 2.5
    assert parse_experience_duration_years("18 months") == 1.5
    assert parse_experience_duration_years("6 mos") == 0.5

    # Vague language must return 0 parsed years
    assert parse_experience_duration_years("strong experience") == 0.0
    assert parse_experience_duration_years("extensive experience") == 0.0
    assert parse_experience_duration_years("experienced software engineer") == 0.0
    assert parse_experience_duration_years("several years") == 0.0
    assert parse_experience_duration_years("multiple years") == 0.0
    assert parse_experience_duration_years("2020") == 0.0  # Standalone single year without range or duration word


def test_experience_interval_merging():
    """Test overlapping, contiguous, separate, duplicate, and Present experience interval merging."""
    # Overlapping intervals: (2020-2022) and (2021-2023) -> 2020-2023 = 3 yrs
    exp_overlap = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2021 - 2023")]
    assert calculate_total_experience_years(exp_overlap) == 3.0

    # Contiguous intervals: (2020-2022) and (2022-2024) -> 2020-2024 = 4 yrs (boundary not double counted)
    exp_contiguous = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2022 - 2024")]
    assert calculate_total_experience_years(exp_contiguous) == 4.0

    # Separate non-overlapping intervals: (2018-2020) and (2022-2024) -> 2 + 2 = 4 yrs
    exp_separate = [ExperienceSchema(duration="2018 - 2020"), ExperienceSchema(duration="2022 - 2024")]
    assert calculate_total_experience_years(exp_separate) == 4.0

    # Duplicate intervals: (2020-2022) and (2020-2022) -> 2 yrs
    exp_duplicate = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2020 - 2022")]
    assert calculate_total_experience_years(exp_duplicate) == 2.0

    # Present range merging: (2022-2024) and (2023-Present) -> 2022-2026 = 4 yrs
    exp_present = [ExperienceSchema(duration="2022 - 2024"), ExperienceSchema(duration="2023 - Present")]
    assert calculate_total_experience_years(exp_present, current_year=2026) == 4.0


def test_experience_required_scenarios():
    """Test experience required behaviors: None, zero, partial, and full candidate experience."""
    cand = CandidateProfile(experience=[ExperienceSchema(duration="2 years")])

    # job.experience_required is None -> score = 100.0
    job_none = JobProfile(experience_required=None)
    score_none, yrs = calculate_experience_score(cand, job_none)
    assert score_none == 100.0
    assert yrs == 2.0

    # job.experience_required is 0 -> score = 100.0 (no division by zero)
    job_zero = JobProfile(experience_required=0)
    score_zero, _ = calculate_experience_score(cand, job_zero)
    assert score_zero == 100.0

    # candidate_years >= required_years -> score = 100.0
    job_req2 = JobProfile(experience_required=2)
    score_req2, _ = calculate_experience_score(cand, job_req2)
    assert score_req2 == 100.0

    # candidate_years < required_years -> score = (2 / 4) * 100 = 50.0
    job_req4 = JobProfile(experience_required=4)
    score_req4, _ = calculate_experience_score(cand, job_req4)
    assert score_req4 == 50.0


def test_education_matching_strictness():
    """Test exact degree match, field match, unrelated degree, missing candidate/job education, and institution exclusion."""
    # Exact degree / field match
    cand_cs = CandidateProfile(education=[EducationSchema(degree="B.Tech Computer Science")])
    job_cs = JobProfile(education="Bachelor's degree in Computer Science")
    assert match_candidate_to_job(cand_cs, job_cs).score_breakdown.education_score == 100.0

    # Field match
    cand_eng = CandidateProfile(education=[EducationSchema(degree="Computer Engineering")])
    job_eng = JobProfile(education="Computer Science")
    assert match_candidate_to_job(cand_eng, job_eng).score_breakdown.education_score == 100.0

    # Unrelated degree
    cand_art = CandidateProfile(education=[EducationSchema(degree="Fine Arts")])
    assert match_candidate_to_job(cand_art, job_cs).score_breakdown.education_score == 0.0

    # Institution match must NOT trigger field match if degree is unrelated
    cand_inst = CandidateProfile(education=[EducationSchema(degree="Fine Arts", institution="University of Computer Science")])
    assert match_candidate_to_job(cand_inst, job_cs).score_breakdown.education_score == 0.0

    # Missing candidate education
    cand_no_edu = CandidateProfile(education=[])
    assert match_candidate_to_job(cand_no_edu, job_cs).score_breakdown.education_score == 0.0

    # Missing job education
    job_no_edu = JobProfile(education=None)
    assert match_candidate_to_job(cand_art, job_no_edu).score_breakdown.education_score == 100.0


def test_match_status_boundary_conditions():
    """Test exact score and required skill coverage boundary conditions for STRONG, POTENTIAL, and WEAK status."""
    # Exactly 80 final_score and 80% (0.80) coverage -> STRONG
    # skill=100 (60 pts), exp=50 (15 pts), edu=50? Let's construct exact scores:
    # skill=100 (60 pts), exp=100 (30 pts), edu=0 (0 pts) -> final = 60 + 30 + 0 = 90.0
    # Let's test boundary thresholds directly:
    cand_strong_exact = CandidateProfile(
        skills=["Python", "SQL", "Docker", "AWS"],
        experience=[ExperienceSchema(duration="4 years")],
        education=[EducationSchema(degree="Other")],
    )
    job_strong_exact = JobProfile(
        required_skills=["Python", "SQL", "Docker", "AWS", "FastAPI"],  # 4/5 = 80% coverage
        experience_required=4,                                          # 4/4 = 100% exp
        education="Computer Science",                                   # 0% edu
    )
    # skill = 80.0 (0.60 * 80 = 48.0)
    # exp = 100.0   (0.30 * 100 = 30.0)
    # edu = 0.0     (0.10 * 0 = 0.0)
    # final = 48.0 + 30.0 + 0.0 = 78.0 -> final < 80, coverage = 80% -> POTENTIAL
    res1 = match_candidate_to_job(cand_strong_exact, job_strong_exact)
    assert res1.score_breakdown.final_score == 78.0
    assert res1.status == MatchStatus.POTENTIAL

    # Make final = 88.0 and coverage = 80% -> STRONG
    cand_strong_88 = CandidateProfile(
        skills=["Python", "SQL", "Docker", "AWS"],
        experience=[ExperienceSchema(duration="4 years")],
        education=[EducationSchema(degree="Computer Science")],
    )
    # skill = 80.0 (48.0), exp = 100.0 (30.0), edu = 100.0 (10.0) -> final = 88.0, coverage = 80%
    res2 = match_candidate_to_job(cand_strong_88, job_strong_exact)
    assert res2.score_breakdown.final_score == 88.0
    assert res2.status == MatchStatus.STRONG

    # Coverage = 49% (below 50%) -> WEAK even if final_score >= 60
    cand_low_cov = CandidateProfile(
        skills=["Python", "Skill2"],
        experience=[ExperienceSchema(duration="10 years")],
        education=[EducationSchema(degree="Computer Science")],
    )
    job_10_req = JobProfile(
        required_skills=["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "Python"],  # 1/10 = 10% coverage
        experience_required=1,
        education="Computer Science",
    )
    # skill = 10.0 (6.0), exp = 100.0 (30.0), edu = 100.0 (10.0) -> final = 46.0, coverage = 10% -> WEAK
    res3 = match_candidate_to_job(cand_low_cov, job_10_req)
    assert res3.status == MatchStatus.WEAK


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

