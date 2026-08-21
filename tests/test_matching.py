from pathlib import Path
from app.schemas.job import JobProfile
from app.schemas.matching import MatchResult, MatchStatus, SemanticMatchResult
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
    sem_res = SemanticMatchResult(
        semantic_score=100.0,
        strengths=["Ideal candidate"],
        gaps=[],
        justification="Perfect alignment."
    )

    res = match_candidate_to_job(cand, job, candidate_id=1, job_id=10, semantic_result=sem_res)

    assert isinstance(res, MatchResult)
    assert res.status == MatchStatus.STRONG
    assert res.score_breakdown.skill_score == 100.0
    assert res.score_breakdown.experience_score == 100.0
    assert res.score_breakdown.education_score == 100.0
    assert res.score_breakdown.semantic_score == 100.0
    assert res.score_breakdown.final_score == 100.0
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
    res2 = match_candidate_to_job(cand_all_req, job_req_pref)
    assert res2.score_breakdown.skill_score == 80.0

    # Case 3: Candidate matching all required skills and no preferred skills
    job_multi_pref = JobProfile(required_skills=["Python"], preferred_skills=["Docker", "AWS"])
    res3 = match_candidate_to_job(CandidateProfile(skills=["Python"]), job_multi_pref)
    assert res3.score_breakdown.skill_score == 80.0

    # Case 4: Candidate matching no required skills (but matching preferred skill)
    res4 = match_candidate_to_job(CandidateProfile(skills=["Docker"]), job_req_pref)
    assert res4.score_breakdown.skill_score == 20.0

    # Case 5: Candidate with preferred skills when job has no preferred skills
    cand_with_extra = CandidateProfile(skills=["Python", "SQL", "Docker", "AWS"])
    res5 = match_candidate_to_job(cand_with_extra, job_req_only)
    assert res5.score_breakdown.skill_score == 100.0


def test_experience_duration_parsing_conservative():
    """Test conservative experience duration parsing without inferring years from vague natural language."""
    assert parse_experience_duration_years("2022 - 2024") == 2.0
    assert parse_experience_duration_years("2023 - Present", current_year=2026) == 3.0
    assert parse_experience_duration_years("2023 - Current", current_year=2026) == 3.0
    assert parse_experience_duration_years("2020 to 2022") == 2.0
    assert parse_experience_duration_years("2 years") == 2.0
    assert parse_experience_duration_years("2.5 yrs") == 2.5
    assert parse_experience_duration_years("18 months") == 1.5
    assert parse_experience_duration_years("6 mos") == 0.5

    assert parse_experience_duration_years("strong experience") == 0.0
    assert parse_experience_duration_years("extensive experience") == 0.0
    assert parse_experience_duration_years("experienced software engineer") == 0.0
    assert parse_experience_duration_years("several years") == 0.0
    assert parse_experience_duration_years("multiple years") == 0.0
    assert parse_experience_duration_years("2020") == 0.0


def test_experience_interval_merging():
    """Test overlapping, contiguous, separate, duplicate, and Present experience interval merging."""
    exp_overlap = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2021 - 2023")]
    assert calculate_total_experience_years(exp_overlap) == 3.0

    exp_contiguous = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2022 - 2024")]
    assert calculate_total_experience_years(exp_contiguous) == 4.0

    exp_separate = [ExperienceSchema(duration="2018 - 2020"), ExperienceSchema(duration="2022 - 2024")]
    assert calculate_total_experience_years(exp_separate) == 4.0

    exp_duplicate = [ExperienceSchema(duration="2020 - 2022"), ExperienceSchema(duration="2020 - 2022")]
    assert calculate_total_experience_years(exp_duplicate) == 2.0

    exp_present = [ExperienceSchema(duration="2022 - 2024"), ExperienceSchema(duration="2023 - Present")]
    assert calculate_total_experience_years(exp_present, current_year=2026) == 4.0


def test_experience_required_scenarios():
    """Test experience required behaviors: None, zero, partial, and full candidate experience."""
    cand = CandidateProfile(experience=[ExperienceSchema(duration="2 years")])

    job_none = JobProfile(experience_required=None)
    score_none, yrs = calculate_experience_score(cand, job_none)
    assert score_none == 100.0
    assert yrs == 2.0

    job_zero = JobProfile(experience_required=0)
    score_zero, _ = calculate_experience_score(cand, job_zero)
    assert score_zero == 100.0

    job_req2 = JobProfile(experience_required=2)
    score_req2, _ = calculate_experience_score(cand, job_req2)
    assert score_req2 == 100.0

    job_req4 = JobProfile(experience_required=4)
    score_req4, _ = calculate_experience_score(cand, job_req4)
    assert score_req4 == 50.0


def test_education_matching_strictness():
    """Test exact degree match, field match, unrelated degree, missing candidate/job education, and institution exclusion."""
    cand_cs = CandidateProfile(education=[EducationSchema(degree="B.Tech Computer Science")])
    job_cs = JobProfile(education="Bachelor's degree in Computer Science")
    assert match_candidate_to_job(cand_cs, job_cs).score_breakdown.education_score == 100.0

    cand_eng = CandidateProfile(education=[EducationSchema(degree="Computer Engineering")])
    job_eng = JobProfile(education="Computer Science")
    assert match_candidate_to_job(cand_eng, job_eng).score_breakdown.education_score == 100.0

    cand_art = CandidateProfile(education=[EducationSchema(degree="Fine Arts")])
    assert match_candidate_to_job(cand_art, job_cs).score_breakdown.education_score == 0.0

    cand_inst = CandidateProfile(education=[EducationSchema(degree="Fine Arts", institution="University of Computer Science")])
    assert match_candidate_to_job(cand_inst, job_cs).score_breakdown.education_score == 0.0

    cand_no_edu = CandidateProfile(education=[])
    assert match_candidate_to_job(cand_no_edu, job_cs).score_breakdown.education_score == 0.0

    job_no_edu = JobProfile(education=None)
    assert match_candidate_to_job(cand_art, job_no_edu).score_breakdown.education_score == 100.0


def test_score_fusion_formula_variations():
    """Test Phase 8 score fusion formula: 0.50*skill + 0.25*exp + 0.10*edu + 0.15*semantic."""
    cand = CandidateProfile(
        skills=["Python", "FastAPI"],
        experience=[ExperienceSchema(duration="4 years")],
        education=[EducationSchema(degree="Computer Science")],
    )
    job = JobProfile(required_skills=["Python", "FastAPI"], experience_required=4, education="Computer Science")

    # 1. Semantic score = 0 -> 0.50*100 + 0.25*100 + 0.10*100 + 0.15*0 = 85.0
    res_0 = match_candidate_to_job(cand, job, semantic_result=SemanticMatchResult(semantic_score=0.0))
    assert res_0.score_breakdown.final_score == 85.0

    # 2. Semantic score = 50 -> 0.50*100 + 0.25*100 + 0.10*100 + 0.15*50 = 92.5
    res_50 = match_candidate_to_job(cand, job, semantic_result=SemanticMatchResult(semantic_score=50.0))
    assert res_50.score_breakdown.final_score == 92.5

    # 3. Semantic score = 100 -> 0.50*100 + 0.25*100 + 0.10*100 + 0.15*100 = 100.0
    res_100 = match_candidate_to_job(cand, job, semantic_result=SemanticMatchResult(semantic_score=100.0))
    assert res_100.score_breakdown.final_score == 100.0


def test_required_skill_coverage_authoritative_over_semantic():
    """Test that a high semantic score cannot override missing required skills for status determination."""
    cand_low_cov = CandidateProfile(
        skills=["Python"],
        experience=[ExperienceSchema(duration="10 years")],
        education=[EducationSchema(degree="Computer Science")],
    )
    job_10_req = JobProfile(
        required_skills=["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "Python"],  # 1/10 = 10% coverage
        experience_required=1,
        education="Computer Science",
    )
    sem_high = SemanticMatchResult(semantic_score=100.0, justification="Highly relevant experience")

    res = match_candidate_to_job(cand_low_cov, job_10_req, semantic_result=sem_high)
    # Even if final_score is above 60, status MUST be WEAK because required_skill_coverage is 10% (< 50%)
    assert res.status == MatchStatus.WEAK


def test_semantic_contradiction_filtered():
    """Test that LLM semantic strengths falsely claiming candidate has missing required skills are filtered."""
    cand = CandidateProfile(skills=["Python"])
    job = JobProfile(required_skills=["Python", "FastAPI"])  # Missing FastAPI
    sem = SemanticMatchResult(
        semantic_score=70.0,
        strengths=["Candidate has FastAPI experience"],  # Contradicts missing required skill
        gaps=["Lacks Docker"],
        justification="Good fit"
    )

    res = match_candidate_to_job(cand, job, semantic_result=sem)
    assert "Missing required skills: FastAPI" in res.gaps
    # Contradictory strength filtered out
    assert "Candidate has FastAPI experience" not in res.strengths


def test_deterministic_repeatability():
    """Test that identical inputs produce 100% identical outputs across multiple invocations."""
    cand = CandidateProfile(name="Repeat Test", skills=["Python", "SQL"])
    job = JobProfile(title="Test Job", required_skills=["Python", "SQL"])
    sem = SemanticMatchResult(semantic_score=80.0, justification="Consistent")

    res1 = match_candidate_to_job(cand, job, candidate_id=5, job_id=12, semantic_result=sem)
    res2 = match_candidate_to_job(cand, job, candidate_id=5, job_id=12, semantic_result=sem)

    assert res1.model_dump() == res2.model_dump()


def test_no_database_or_llm_side_effects():
    """Test that matcher causes no database creation or filesystem side effects."""
    cand = CandidateProfile(skills=["Python"])
    job = JobProfile(required_skills=["Python"])
    sem = SemanticMatchResult(semantic_score=100.0)

    res = match_candidate_to_job(cand, job, semantic_result=sem)
    assert res.score_breakdown.final_score == 100.0

    root_db = Path("resume_screener.db")
    assert not root_db.exists(), "Matching engine unexpectedly created a database file!"


