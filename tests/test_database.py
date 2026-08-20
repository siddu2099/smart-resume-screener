"""Database infrastructure and ORM model unit tests."""

import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, event
from sqlalchemy.orm import sessionmaker

from app.database.database import Base, init_db
from app.models import Candidate, Education, Experience, Job, Match, Skill


def create_test_db():
    """Create an isolated in-memory SQLite engine and session factory."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Enable foreign keys for SQLite
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(engine_override=test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    return test_engine, TestingSessionLocal


def test_database_initialization_and_tables():
    """Test that init_db creates all expected ORM tables."""
    engine, _ = create_test_db()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "candidates",
        "skills",
        "experiences",
        "educations",
        "jobs",
        "matches",
    }
    assert expected_tables.issubset(tables)


def test_candidate_creation_and_relationships():
    """Test candidate creation along with linked skills, experience, and education."""
    _, SessionFactory = create_test_db()
    db = SessionFactory()

    candidate = Candidate(
        name="Test Candidate",
        email="test@example.com",
        phone="+1234567890",
        resume_filename="resume_test.pdf",
        resume_text="Extracted resume text content.",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    assert candidate.id is not None
    assert candidate.name == "Test Candidate"

    # Add Skill, Experience, Education
    skill = Skill(candidate_id=candidate.id, skill_name="Python")
    exp = Experience(
        candidate_id=candidate.id,
        company="Example Corp",
        role="Software Engineer",
        duration="2 years",
        description="Developed backend services.",
    )
    edu = Education(
        candidate_id=candidate.id,
        degree="B.Tech Computer Science",
        institution="University Exam",
        year="2024",
    )

    db.add_all([skill, exp, edu])
    db.commit()

    db.refresh(candidate)
    assert len(candidate.skills) == 1
    assert candidate.skills[0].skill_name == "Python"

    assert len(candidate.experience) == 1
    assert candidate.experience[0].company == "Example Corp"

    assert len(candidate.education) == 1
    assert candidate.education[0].degree == "B.Tech Computer Science"

    db.close()


def test_job_and_match_creation():
    """Test Job creation and Candidate-Job Match record linking."""
    _, SessionFactory = create_test_db()
    db = SessionFactory()

    candidate = Candidate(name="Jane Doe", email="jane@example.com")
    job = Job(
        title="Backend Engineer",
        description="Python FastAPI and SQLAlchemy developer.",
    )
    db.add_all([candidate, job])
    db.commit()
    db.refresh(candidate)
    db.refresh(job)

    match = Match(
        candidate_id=candidate.id,
        job_id=job.id,
        skill_score=0.9,
        experience_score=0.85,
        education_score=0.8,
        semantic_score=0.88,
        final_score=0.87,
        status="shortlisted",
        justification="Strong match in Python and database design.",
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    assert match.id is not None
    assert match.candidate.name == "Jane Doe"
    assert match.job.title == "Backend Engineer"
    assert len(candidate.matches) == 1
    assert len(job.matches) == 1

    db.close()


def test_candidate_cascade_delete():
    """Test that deleting a Candidate cascades to skills, experience, education, and matches."""
    _, SessionFactory = create_test_db()
    db = SessionFactory()

    candidate = Candidate(name="Cascade Target")
    job = Job(title="DevOps Engineer", description="CI/CD and Cloud infrastructure.")
    db.add_all([candidate, job])
    db.commit()

    skill = Skill(candidate_id=candidate.id, skill_name="Docker")
    exp = Experience(candidate_id=candidate.id, company="Cloud Inc")
    edu = Education(candidate_id=candidate.id, degree="B.S.")
    match = Match(candidate_id=candidate.id, job_id=job.id, final_score=0.75)

    db.add_all([skill, exp, edu, match])
    db.commit()

    # Delete candidate
    db.delete(candidate)
    db.commit()

    assert db.query(Candidate).filter_by(id=candidate.id).first() is None
    assert db.query(Skill).filter_by(candidate_id=candidate.id).all() == []
    assert db.query(Experience).filter_by(candidate_id=candidate.id).all() == []
    assert db.query(Education).filter_by(candidate_id=candidate.id).all() == []
    assert db.query(Match).filter_by(candidate_id=candidate.id).all() == []

    db.close()


def test_job_cascade_delete():
    """Test that deleting a Job cascades to associated Match records."""
    _, SessionFactory = create_test_db()
    db = SessionFactory()

    candidate = Candidate(name="John Smith")
    job = Job(title="Data Scientist", description="ML and Python analysis.")
    db.add_all([candidate, job])
    db.commit()

    match = Match(candidate_id=candidate.id, job_id=job.id, final_score=0.92)
    db.add(match)
    db.commit()

    # Delete job
    db.delete(job)
    db.commit()

    assert db.query(Job).filter_by(id=job.id).first() is None
    assert db.query(Match).filter_by(job_id=job.id).all() == []
    # Candidate should still exist
    assert db.query(Candidate).filter_by(id=candidate.id).first() is not None

    db.close()


def test_no_db_file_created_in_root():
    """Verify that importing models/database and running tests creates no .db file in root."""
    root_db_path = Path("resume_screener.db")
    assert not root_db_path.exists(), "Found unexpected database file created in workspace root!"
