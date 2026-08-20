"""Candidate-Job Match SQLAlchemy ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.job import Job


class Match(Base):
    """Candidate-Job Match result model."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    skill_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    experience_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    education_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    semantic_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="matches")
    job: Mapped["Job"] = relationship("Job", back_populates="matches")
