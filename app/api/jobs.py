"""Job posting API endpoints."""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.job import JobCreateRequest, JobResponse
from app.services.job_service import create_job_from_description

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest job description and create job posting",
)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Extract structured job profile from raw job description and persist into database."""
    return create_job_from_description(description=payload.description, db=db)
