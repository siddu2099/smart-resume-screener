"""Service orchestration and database persistence for job postings."""

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobProfile, JobResponse
from app.services.job_parser import JobParsingError, extract_job_profile
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def job_orm_to_domain(job: Job, llm_service: Optional[LLMService] = None) -> JobProfile:
    """Convert a Job SQLAlchemy ORM model to a JobProfile Pydantic domain model.

    Parses job description text using extract_job_profile.
    """
    try:
        return extract_job_profile(job.description, llm_service=llm_service)
    except Exception:
        # Fallback if raw re-parsing fails
        return JobProfile(title=job.title)


def job_orm_to_response(
    job: Job,
    profile: Optional[JobProfile] = None,
    llm_service: Optional[LLMService] = None,
) -> JobResponse:
    """Convert a Job SQLAlchemy ORM model to a JobResponse API schema."""
    job_profile = profile or job_orm_to_domain(job, llm_service=llm_service)
    return JobResponse(
        job_id=job.id,
        title=job_profile.title or job.title,
        required_skills=job_profile.required_skills,
        preferred_skills=job_profile.preferred_skills,
        experience_required=job_profile.experience_required,
        education=job_profile.education,
        responsibilities=job_profile.responsibilities,
        description=job.description,
        created_at=job.created_at,
    )


def create_job_from_description(
    description: str,
    db: Session,
    llm_service: Optional[LLMService] = None,
) -> JobResponse:
    """Validate description, extract JobProfile using LLM, and persist Job into database.

    Args:
        description: Raw job posting description text.
        db: SQLAlchemy database session.
        llm_service: Optional LLMService instance.

    Returns:
        JobResponse schema containing job details and DB id.
    """
    if not description or not description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description cannot be empty or whitespace only",
        )

    try:
        profile = extract_job_profile(description, llm_service=llm_service)
    except JobParsingError as err:
        logger.error("Job LLM extraction failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract job profile from description text: {err}",
        ) from err

    job_title = profile.title or "Untitled Position"

    try:
        job_orm = Job(title=job_title, description=description)
        db.add(job_orm)
        db.commit()
        db.refresh(job_orm)
    except Exception as err:
        db.rollback()
        logger.error("Database persistence failed for job '%s': %s", job_title, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist job posting into database",
        ) from err

    return job_orm_to_response(job_orm, profile=profile)


def get_job_by_id(job_id: int, db: Session) -> Job:
    """Retrieve Job ORM model by ID or raise HTTP 404."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    return job
