"""Resume ingestion API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.resume import CandidateResponse
from app.services.candidate_service import create_candidate_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a candidate resume PDF",
)
async def upload_resume(
    file: Annotated[UploadFile, File(description="Candidate resume PDF file")],
    db: Session = Depends(get_db),
) -> CandidateResponse:
    """Ingest resume PDF, extract candidate profile, and persist into database."""
    filename = file.filename or "resume.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF resume files (.pdf) are supported",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty",
        )

    return create_candidate_from_pdf(file_bytes=file_bytes, filename=filename, db=db)
