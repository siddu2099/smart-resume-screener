"""Service orchestration and database persistence for candidate resumes."""

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, Education, Experience, Skill
from app.schemas.resume import CandidateProfile, CandidateResponse, EducationSchema, ExperienceSchema
from app.services.llm_service import LLMService
from app.services.pdf_parser import ResumeExtractionError, extract_text_from_pdf
from app.services.resume_parser import ResumeParsingError, extract_resume_profile

logger = logging.getLogger(__name__)


def candidate_orm_to_domain(candidate: Candidate) -> CandidateProfile:
    """Convert a Candidate SQLAlchemy ORM model to a CandidateProfile Pydantic domain model.

    Preserves technical terms (e.g. C++, C#, .NET, Node.js, CI/CD).
    """
    skills = [s.skill_name for s in candidate.skills if s.skill_name]
    experiences = [
        ExperienceSchema(
            company=exp.company,
            role=exp.role,
            duration=exp.duration,
            description=exp.description,
        )
        for exp in candidate.experience
    ]
    educations = [
        EducationSchema(
            degree=edu.degree,
            institution=edu.institution,
            year=edu.year,
        )
        for edu in candidate.education
    ]

    return CandidateProfile(
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        skills=skills,
        experience=experiences,
        education=educations,
    )


def candidate_orm_to_response(candidate: Candidate) -> CandidateResponse:
    """Convert a Candidate SQLAlchemy ORM model to a CandidateResponse API schema."""
    domain_profile = candidate_orm_to_domain(candidate)
    return CandidateResponse(
        candidate_id=candidate.id,
        name=domain_profile.name,
        email=domain_profile.email,
        phone=domain_profile.phone,
        skills=domain_profile.skills,
        experience=domain_profile.experience,
        education=domain_profile.education,
        resume_filename=candidate.resume_filename,
        created_at=candidate.created_at,
    )


def create_candidate_from_pdf(
    file_bytes: bytes,
    filename: str,
    db: Session,
    llm_service: Optional[LLMService] = None,
) -> CandidateResponse:
    """Validate, parse, extract, and persist candidate resume PDF.

    Args:
        file_bytes: Raw binary bytes of uploaded PDF file.
        filename: Name of the uploaded file.
        db: SQLAlchemy database session.
        llm_service: Optional LLMService instance.

    Returns:
        CandidateResponse schema containing candidate details and DB id.
    """
    try:
        resume_text = extract_text_from_pdf(file_bytes)
    except ResumeExtractionError as err:
        logger.warning("PDF extraction failed for %s: %s", filename, err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unparseable PDF file: {err}",
        ) from err

    try:
        profile = extract_resume_profile(resume_text, llm_service=llm_service)
    except ResumeParsingError as err:
        logger.error("Resume LLM extraction failed for %s: %s", filename, err)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract candidate profile from resume text: {err}",
        ) from err

    # Fallback candidate name if unextracted
    cand_name = profile.name or filename.rsplit(".", 1)[0] or "Unknown Candidate"

    try:
        candidate_orm = Candidate(
            name=cand_name,
            email=profile.email,
            phone=profile.phone,
            resume_filename=filename,
            resume_text=resume_text,
        )
        db.add(candidate_orm)
        db.flush()  # Populate candidate_orm.id

        # Persist Skills
        for skill_str in profile.skills:
            if skill_str and skill_str.strip():
                skill_orm = Skill(candidate_id=candidate_orm.id, skill_name=skill_str.strip())
                db.add(skill_orm)

        # Persist Experience
        for exp_entry in profile.experience:
            exp_orm = Experience(
                candidate_id=candidate_orm.id,
                company=exp_entry.company,
                role=exp_entry.role,
                duration=exp_entry.duration,
                description=exp_entry.description,
            )
            db.add(exp_orm)

        # Persist Education
        for edu_entry in profile.education:
            edu_orm = Education(
                candidate_id=candidate_orm.id,
                degree=edu_entry.degree,
                institution=edu_entry.institution,
                year=edu_entry.year,
            )
            db.add(edu_orm)

        db.commit()
        db.refresh(candidate_orm)

    except Exception as err:
        db.rollback()
        logger.error("Database persistence failed for candidate %s: %s", filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist candidate profile into database",
        ) from err

    return candidate_orm_to_response(candidate_orm)


def get_candidate_by_id(candidate_id: int, db: Session) -> Candidate:
    """Retrieve Candidate ORM model by ID or raise HTTP 404."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found",
        )
    return candidate
