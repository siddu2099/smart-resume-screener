"""Matching and shortlist API endpoints."""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.matching import MatchRequest, MatchResult, ShortlistResult
from app.services.match_service import create_or_update_match, get_job_shortlist, get_match_by_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Matching & Shortlist"])


@router.post(
    "/matches",
    response_model=MatchResult,
    status_code=status.HTTP_200_OK,
    summary="Match candidate against job posting and persist result",
)
def create_match(
    payload: MatchRequest,
    db: Session = Depends(get_db),
) -> MatchResult:
    """Evaluate candidate against job using deterministic + semantic score fusion and persist match."""
    return create_or_update_match(
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        db=db,
    )


@router.get(
    "/matches/{match_id}",
    response_model=MatchResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve candidate-job match evaluation by ID",
)
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
) -> MatchResult:
    """Retrieve persisted match result by match_id."""
    return get_match_by_id(match_id=match_id, db=db)


@router.get(
    "/jobs/{job_id}/shortlist",
    response_model=ShortlistResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve ranked candidate shortlist for a job posting",
)
def get_shortlist(
    job_id: int,
    db: Session = Depends(get_db),
) -> ShortlistResult:
    """Retrieve ranked candidate shortlist sorted deterministically by final_score DESC, candidate_id ASC."""
    return get_job_shortlist(job_id=job_id, db=db)
