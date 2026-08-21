"""Service orchestration, score fusion, database persistence, and shortlisting for matching."""

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import Match
from app.schemas.matching import MatchResult, MatchStatus, ScoreBreakdown, ShortlistCandidate, ShortlistResult
from app.services.candidate_service import candidate_orm_to_domain, get_candidate_by_id
from app.services.job_service import get_job_by_id, job_orm_to_domain
from app.services.llm_service import LLMService, LLMServiceError
from app.services.matcher import match_candidate_to_job
from app.services.semantic_matcher import SemanticMatchingError, evaluate_semantic_match

logger = logging.getLogger(__name__)


def create_or_update_match(
    candidate_id: int,
    job_id: int,
    db: Session,
    llm_service: Optional[LLMService] = None,
) -> MatchResult:
    """Orchestrate candidate-job matching, semantic LLM evaluation, score fusion, and DB upsert.

    Args:
        candidate_id: Candidate DB primary key.
        job_id: Job DB primary key.
        db: SQLAlchemy database session.
        llm_service: Optional LLMService instance.

    Returns:
        Complete MatchResult schema.

    Raises:
        HTTPException 404: If candidate or job is not found.
        HTTPException 503: If semantic matching fails or Ollama is unavailable (no DB record created).
        HTTPException 500: On database transaction failure.
    """
    candidate_orm = get_candidate_by_id(candidate_id, db)
    job_orm = get_job_by_id(job_id, db)

    candidate_profile = candidate_orm_to_domain(candidate_orm)
    job_profile = job_orm_to_domain(job_orm, llm_service=llm_service)

    # 1. Run LLM Semantic Evaluation (Failure -> HTTP 503 without DB write)
    try:
        semantic_result = evaluate_semantic_match(
            candidate_profile,
            job_profile,
            llm_service=llm_service,
        )
    except (LLMServiceError, SemanticMatchingError) as err:
        logger.error(
            "Semantic matching failed for candidate_id=%d, job_id=%d: %s",
            candidate_id,
            job_id,
            err,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Semantic matching evaluation failed or LLM service is unavailable: {err}",
        ) from err
    except Exception as err:
        logger.error(
            "Unexpected error during semantic matching for candidate_id=%d, job_id=%d: %s",
            candidate_id,
            job_id,
            err,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Semantic matching failed: {err}",
        ) from err

    # 2. Run Deterministic Score Fusion
    match_result = match_candidate_to_job(
        candidate=candidate_profile,
        job=job_profile,
        candidate_id=candidate_id,
        job_id=job_id,
        semantic_result=semantic_result,
    )

    # 3. DB Persistence / Upsert (One current match per candidate-job pair)
    try:
        existing_match = (
            db.query(Match)
            .filter(Match.candidate_id == candidate_id, Match.job_id == job_id)
            .first()
        )

        if existing_match:
            match_orm = existing_match
            match_orm.skill_score = match_result.score_breakdown.skill_score
            match_orm.experience_score = match_result.score_breakdown.experience_score
            match_orm.education_score = match_result.score_breakdown.education_score
            match_orm.semantic_score = match_result.score_breakdown.semantic_score
            match_orm.final_score = match_result.score_breakdown.final_score
            match_orm.status = match_result.status.value
            match_orm.justification = match_result.justification
        else:
            match_orm = Match(
                candidate_id=candidate_id,
                job_id=job_id,
                skill_score=match_result.score_breakdown.skill_score,
                experience_score=match_result.score_breakdown.experience_score,
                education_score=match_result.score_breakdown.education_score,
                semantic_score=match_result.score_breakdown.semantic_score,
                final_score=match_result.score_breakdown.final_score,
                status=match_result.status.value,
                justification=match_result.justification,
            )
            db.add(match_orm)

        db.commit()
        db.refresh(match_orm)

    except Exception as err:
        db.rollback()
        logger.error("Database error during match persistence: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist match evaluation into database",
        ) from err

    return match_result


def get_match_by_id(
    match_id: int,
    db: Session,
    llm_service: Optional[LLMService] = None,
) -> MatchResult:
    """Retrieve Match result by ID or raise HTTP 404."""
    match_orm = db.query(Match).filter(Match.id == match_id).first()
    if not match_orm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match evaluation with ID {match_id} not found",
        )

    candidate_orm = db.query(Candidate).filter(Candidate.id == match_orm.candidate_id).first()
    job_orm = db.query(Job).filter(Job.id == match_orm.job_id).first()

    if not candidate_orm or not job_orm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated candidate or job record no longer exists",
        )

    candidate_profile = candidate_orm_to_domain(candidate_orm)
    job_profile = job_orm_to_domain(job_orm, llm_service=llm_service)

    # Re-evaluate deterministic facts to reconstruct MatchResult
    match_result = match_candidate_to_job(candidate_profile, job_profile)

    # Override stored scores, status, and justification from DB record
    status_enum = MatchStatus(match_orm.status) if match_orm.status else match_result.status

    score_breakdown = ScoreBreakdown(
        skill_score=match_orm.skill_score or 0.0,
        experience_score=match_orm.experience_score or 0.0,
        education_score=match_orm.education_score or 0.0,
        semantic_score=match_orm.semantic_score or 0.0,
        final_score=match_orm.final_score or 0.0,
    )

    return MatchResult(
        candidate_id=match_orm.candidate_id,
        job_id=match_orm.job_id,
        score_breakdown=score_breakdown,
        status=status_enum,
        strengths=match_result.strengths,
        gaps=match_result.gaps,
        matched_required_skills=match_result.matched_required_skills,
        missing_required_skills=match_result.missing_required_skills,
        matched_preferred_skills=match_result.matched_preferred_skills,
        justification=match_orm.justification or match_result.justification,
    )


def get_job_shortlist(
    job_id: int,
    db: Session,
    llm_service: Optional[LLMService] = None,
) -> ShortlistResult:
    """Retrieve ranked candidate shortlist for a job posting.

    Sorts candidates deterministically by:
    1. final_score DESC
    2. candidate_id ASC (tie-breaker)
    """
    job_orm = get_job_by_id(job_id, db)

    # Query all matches for job_id
    matches = db.query(Match).filter(Match.job_id == job_id).all()

    # Pick latest match for each candidate_id
    candidate_latest_match: dict[int, Match] = {}
    for m in matches:
        if m.candidate_id not in candidate_latest_match or m.id > candidate_latest_match[m.candidate_id].id:
            candidate_latest_match[m.candidate_id] = m

    unique_matches = list(candidate_latest_match.values())

    # Deterministic sorting: final_score DESC, candidate_id ASC
    unique_matches.sort(key=lambda m: (-(m.final_score or 0.0), m.candidate_id))

    shortlist_candidates: list[ShortlistCandidate] = []
    for m in unique_matches:
        candidate_orm = db.query(Candidate).filter(Candidate.id == m.candidate_id).first()
        cand_name = candidate_orm.name if candidate_orm else f"Candidate #{m.candidate_id}"

        # Load domain profiles for strengths & gaps
        if candidate_orm:
            cand_domain = candidate_orm_to_domain(candidate_orm)
            job_domain = job_orm_to_domain(job_orm, llm_service=llm_service)
            det_res = match_candidate_to_job(cand_domain, job_domain)
            strengths = det_res.strengths
            gaps = det_res.gaps
        else:
            strengths = []
            gaps = []

        status_enum = MatchStatus(m.status) if m.status else MatchStatus.WEAK

        shortlist_candidates.append(
            ShortlistCandidate(
                candidate_id=m.candidate_id,
                candidate_name=cand_name,
                final_score=m.final_score or 0.0,
                status=status_enum,
                justification=m.justification or "",
                strengths=strengths,
                gaps=gaps,
            )
        )

    return ShortlistResult(job_id=job_orm.id, candidates=shortlist_candidates)
