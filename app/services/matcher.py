"""100% Deterministic candidate-to-job matching engine."""

import datetime
import re
from typing import Optional, Union

from app.schemas.job import JobProfile
from app.schemas.matching import MatchResult, MatchStatus, ScoreBreakdown
from app.schemas.resume import CandidateProfile, ExperienceSchema


def normalize_skill(skill: str) -> str:
    """Normalize skill string by stripping whitespace and converting to lowercase.

    Preserves technical symbols (+, #, ., /, -) for terms like C++, C#, .NET, Node.js, CI/CD.
    """
    if not skill:
        return ""
    return skill.strip().lower()


def parse_experience_duration_years(duration_str: Optional[str], current_year: int = 2026) -> float:
    """Conservatively parse an experience duration string into years.

    Supported formats:
    - "YYYY - YYYY" / "YYYY to YYYY" (e.g. "2022 - 2024" -> 2.0 years using approximate calendar-year model)
    - "YYYY - Present" / "YYYY - Current" (e.g. "2023 - Present" -> 3.0 years using current_year)
    - "X years" / "X yrs" / "X yr" (e.g. "2 years" -> 2.0)
    - "X months" / "X mos" / "X mo" (e.g. "18 months" -> 1.5)

    Unparseable, ambiguous, or vague strings (e.g. "strong experience", "several years") return 0.0.
    """
    if not duration_str:
        return 0.0

    duration_clean = duration_str.strip().lower()

    # 1. Match year range: "YYYY - YYYY" or "YYYY - Present" / "YYYY to YYYY"
    range_match = re.search(
        r"\b(19\d{2}|20\d{2})\s*(?:[-–—]|to)\s*(present|current|19\d{2}|20\d{2})\b",
        duration_clean,
    )
    if range_match:
        start_yr = int(range_match.group(1))
        end_str = range_match.group(2)
        end_yr = current_year if end_str in ("present", "current") else int(end_str)
        return float(max(0, end_yr - start_yr))

    # 2. Match "X years" / "X yrs" / "X yr"
    years_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)\b", duration_clean)
    if years_match:
        return float(years_match.group(1))

    # 3. Match "X months" / "X mos" / "X mo"
    months_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:months?|mos?|mo)\b", duration_clean)
    if months_match:
        return float(months_match.group(1)) / 12.0

    return 0.0


def calculate_total_experience_years(experiences: list[ExperienceSchema], current_year: int = 2026) -> float:
    """Calculate candidate's total experience in years by parsing and merging overlapping/contiguous year intervals."""
    intervals: list[tuple[int, int]] = []
    standalone_years = 0.0

    for exp in experiences:
        if not exp.duration:
            continue
        duration_clean = exp.duration.strip().lower()

        range_match = re.search(
            r"\b(19\d{2}|20\d{2})\s*(?:[-–—]|to)\s*(present|current|19\d{2}|20\d{2})\b",
            duration_clean,
        )
        if range_match:
            start_yr = int(range_match.group(1))
            end_str = range_match.group(2)
            end_yr = current_year if end_str in ("present", "current") else int(end_str)
            if end_yr >= start_yr:
                intervals.append((start_yr, end_yr))
            continue

        parsed_yr = parse_experience_duration_years(exp.duration, current_year=current_year)
        standalone_years += parsed_yr

    if not intervals:
        return round(standalone_years, 2)

    # Sort and merge overlapping or contiguous date intervals
    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if not merged:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:  # Overlapping or contiguous
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

    interval_years = sum(end - start for start, end in merged)
    return round(interval_years + standalone_years, 2)


def calculate_experience_score(candidate: CandidateProfile, job: JobProfile) -> tuple[float, float]:
    """Calculate experience match score (0-100) and candidate total experience years.

    Rules:
    - If job.experience_required is None: score = 100.0.
    - If job.experience_required is numeric minimum (e.g. 3):
        - Candidate years >= required years -> 100.0
        - Candidate years < required years -> (candidate_years / required_years) * 100.0
    """
    candidate_years = calculate_total_experience_years(candidate.experience)

    if job.experience_required is None:
        return 100.0, candidate_years

    try:
        req_years = float(job.experience_required)
    except (ValueError, TypeError):
        return 100.0, candidate_years

    if req_years <= 0:
        return 100.0, candidate_years

    if candidate_years >= req_years:
        score = 100.0
    else:
        score = (candidate_years / req_years) * 100.0

    return round(max(0.0, min(100.0, score)), 2), candidate_years


GENERIC_EDU_TOKENS = {
    "in", "or", "and", "a", "an", "the", "field", "related", "with", "of",
    "degree", "bachelor", "bachelors", "bachelor's", "master", "masters",
    "master's", "bs", "ba", "ms", "ma", "phd", "doctorate", "diploma", "major"
}


def calculate_education_score(candidate: CandidateProfile, job: JobProfile) -> float:
    """Calculate education match score (0.0 or 100.0).

    Rules:
    - If job.education is None or empty: score = 100.0.
    - If job.education exists: score = 100.0 if candidate degree matches degree/field keywords, else 0.0.
    """
    if not job.education or not job.education.strip():
        return 100.0

    if not candidate.education:
        return 0.0

    req_edu_norm = job.education.strip().lower()
    req_tokens = set(re.findall(r"\b[a-z0-9\.#+]+\b", req_edu_norm))
    req_field_keywords = req_tokens - GENERIC_EDU_TOKENS

    for edu in candidate.education:
        if not edu.degree or not edu.degree.strip():
            continue
        cand_degree_norm = edu.degree.strip().lower()

        if req_edu_norm in cand_degree_norm or cand_degree_norm in req_edu_norm:
            return 100.0

        cand_words = set(re.findall(r"\b[a-z0-9\.#+]+\b", cand_degree_norm))

        if req_field_keywords:
            if req_field_keywords.intersection(cand_words):
                return 100.0
        else:
            if req_tokens.intersection(cand_words):
                return 100.0

    return 0.0


def match_candidate_to_job(
    candidate: CandidateProfile,
    job: JobProfile,
    candidate_id: Union[int, str] = 1,
    job_id: Union[int, str] = 1,
) -> MatchResult:
    """Deterministic candidate-to-job matching engine.

    Evaluates a CandidateProfile against a JobProfile and returns a deterministic MatchResult.
    Note: semantic_score is intentionally set to 0.0 as LLM semantic matching is deferred to Phase 8.

    Args:
        candidate: CandidateProfile domain schema instance.
        job: JobProfile domain schema instance.
        candidate_id: Integer or string candidate identifier.
        job_id: Integer or string job identifier.

    Returns:
        MatchResult domain schema instance.
    """
    c_id = int(candidate_id) if str(candidate_id).isdigit() else 1
    j_id = int(job_id) if str(job_id).isdigit() else 1

    # --- 1. Skill Matching ---
    candidate_norm_map = {}
    for s in candidate.skills:
        n = normalize_skill(s)
        if n and n not in candidate_norm_map:
            candidate_norm_map[n] = s

    # Deduplicate required skills while preserving job skill order
    seen_req = set()
    dedup_required = []
    for s in job.required_skills:
        n = normalize_skill(s)
        if n and n not in seen_req:
            seen_req.add(n)
            dedup_required.append(s)

    matched_required = [s for s in dedup_required if normalize_skill(s) in candidate_norm_map]
    missing_required = [s for s in dedup_required if normalize_skill(s) not in candidate_norm_map]

    # Deduplicate preferred skills while preserving job skill order
    seen_pref = set()
    dedup_preferred = []
    for s in job.preferred_skills:
        n = normalize_skill(s)
        if n and n not in seen_pref:
            seen_pref.add(n)
            dedup_preferred.append(s)

    matched_preferred = [s for s in dedup_preferred if normalize_skill(s) in candidate_norm_map]

    if dedup_required:
        req_score = (len(matched_required) / len(dedup_required)) * 100.0
    else:
        req_score = 100.0

    if dedup_preferred:
        pref_score = (len(matched_preferred) / len(dedup_preferred)) * 100.0
        skill_score = 0.80 * req_score + 0.20 * pref_score
    else:
        pref_score = 0.0
        skill_score = req_score

    skill_score = round(max(0.0, min(100.0, skill_score)), 2)

    # --- 2. Experience Matching ---
    exp_score, candidate_years = calculate_experience_score(candidate, job)

    # --- 3. Education Matching ---
    edu_score = calculate_education_score(candidate, job)

    # --- 4. Final Deterministic Score Calculation ---
    # Baseline formula: 60% skill + 30% experience + 10% education
    # Note: semantic_score is set to 0.0 (semantic matching deferred)
    semantic_score = 0.0
    final_score = round(max(0.0, min(100.0, 0.60 * skill_score + 0.30 * exp_score + 0.10 * edu_score)), 2)

    # --- 5. Status Classification ---
    req_coverage = (len(matched_required) / len(dedup_required)) if dedup_required else 1.0

    if final_score >= 80.0 and req_coverage >= 0.80:
        status = MatchStatus.STRONG
    elif final_score >= 60.0 and req_coverage >= 0.50:
        status = MatchStatus.POTENTIAL
    else:
        status = MatchStatus.WEAK

    # --- 6. Strengths, Gaps, and Justification ---
    strengths: list[str] = []
    gaps: list[str] = []

    if dedup_required:
        strengths.append(f"Matched {len(matched_required)} of {len(dedup_required)} required skills")
        if missing_required:
            gaps.append(f"Missing required skills: {', '.join(missing_required)}")
    else:
        strengths.append("No specific required skills specified by job posting")

    if matched_preferred:
        strengths.append(f"Matched {len(matched_preferred)} of {len(dedup_preferred)} preferred skills ({', '.join(matched_preferred)})")

    if job.experience_required is not None:
        try:
            req_yrs = float(job.experience_required)
            if candidate_years >= req_yrs:
                strengths.append(f"Meets minimum experience requirement ({candidate_years} yrs vs {req_yrs} yrs required)")
            else:
                gaps.append(f"Candidate experience ({candidate_years} yrs) is below required minimum ({req_yrs} yrs)")
        except (ValueError, TypeError):
            pass
    else:
        strengths.append("No explicit minimum experience requirement specified")

    if job.education and job.education.strip():
        if edu_score == 100.0:
            strengths.append("Satisfies education requirement")
        else:
            gaps.append(f"Education requirement not matched: {job.education}")
    else:
        strengths.append("No explicit education requirement specified")

    justification_parts = [
        f"Deterministic Match Evaluation ({status.value}):",
        f"Skill score is {skill_score}% (matched {len(matched_required)}/{len(dedup_required)} required skills).",
        f"Experience score is {exp_score}% (candidate has {candidate_years} years of experience).",
        f"Education score is {edu_score}%.",
        "Semantic LLM scoring is currently deferred (baseline 0.0%).",
    ]
    justification = " ".join(justification_parts)

    score_breakdown = ScoreBreakdown(
        skill_score=skill_score,
        experience_score=exp_score,
        education_score=edu_score,
        semantic_score=semantic_score,
        final_score=final_score,
    )

    return MatchResult(
        candidate_id=c_id,
        job_id=j_id,
        score_breakdown=score_breakdown,
        status=status,
        strengths=strengths,
        gaps=gaps,
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        justification=justification,
    )
