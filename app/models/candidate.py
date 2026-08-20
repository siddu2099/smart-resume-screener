"""Candidate, Skill, Experience, and Education SQLAlchemy ORM models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.models.match import Match


class Candidate(Base):
    """Candidate profile model."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resume_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships with cascade deletion
    skills: Mapped[list["Skill"]] = relationship(
        "Skill", back_populates="candidate", cascade="all, delete-orphan"
    )
    experience: Mapped[list["Experience"]] = relationship(
        "Experience", back_populates="candidate", cascade="all, delete-orphan"
    )
    education: Mapped[list["Education"]] = relationship(
        "Education", back_populates="candidate", cascade="all, delete-orphan"
    )
    matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="candidate", cascade="all, delete-orphan"
    )


class Skill(Base):
    """Candidate skill model."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="skills")


class Experience(Base):
    """Candidate work experience model."""

    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="experience")


class Education(Base):
    """Candidate education model."""

    __tablename__ = "educations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    degree: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    institution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    year: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="education")
