"""Phase 9 integration test suite for REST API endpoints, database persistence, and shortlisting."""

from unittest.mock import patch

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.match import Match
from app.schemas.job import JobProfile
from app.schemas.matching import SemanticMatchResult
from app.schemas.resume import CandidateProfile, EducationSchema, ExperienceSchema
from app.services.llm_service import LLMServiceError

# Create isolated in-memory SQLite database for integration tests using StaticPool
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables before each test and drop them after test completion."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    """FastAPI get_db dependency override for isolated test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_minimal_pdf_bytes(text_content: str = "John Doe\nSoftware Engineer\nPython, SQL") -> bytes:
    """Helper to generate minimal valid PDF bytes containing text_content."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text_content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# --- 1. POST /resumes Tests ---

def test_post_resumes_valid_pdf(monkeypatch):
    """Test POST /resumes ingests valid PDF, extracts profile, and persists candidate into database."""
    mock_profile = CandidateProfile(
        name="Alice Smith",
        email="alice@example.com",
        phone="555-0199",
        skills=["Python", "FastAPI", "SQL", "C++", ".NET"],
        experience=[ExperienceSchema(company="Tech Corp", role="Dev", duration="2020 - 2024")],
        education=[EducationSchema(degree="B.S. Computer Science")],
    )
    monkeypatch.setattr("app.services.candidate_service.extract_resume_profile", lambda *args, **kwargs: mock_profile)

    pdf_bytes = create_minimal_pdf_bytes("Alice Smith Resume Text")
    files = {"file": ("alice_resume.pdf", pdf_bytes, "application/pdf")}

    response = client.post("/resumes", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["candidate_id"] > 0
    assert data["name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert data["skills"] == ["Python", "FastAPI", "SQL", "C++", ".NET"]

    # Verify DB persistence
    db = TestingSessionLocal()
    cand = db.query(Candidate).filter(Candidate.id == data["candidate_id"]).first()
    assert cand is not None
    assert cand.name == "Alice Smith"
    assert len(cand.skills) == 5
    assert len(cand.experience) == 1
    assert len(cand.education) == 1
    db.close()


def test_post_resumes_non_pdf():
    """Test POST /resumes rejects non-PDF file upload with 400 Bad Request."""
    files = {"file": ("resume.txt", b"Plain text content", "text/plain")}
    response = client.post("/resumes", files=files)
    assert response.status_code == 400
    assert "Only PDF resume files" in response.json()["detail"]


def test_post_resumes_empty_file():
    """Test POST /resumes rejects empty file upload with 400 Bad Request."""
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/resumes", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


# --- 2. POST /jobs Tests ---

def test_post_jobs_valid_description(monkeypatch):
    """Test POST /jobs ingests description, extracts JobProfile, and persists job into database."""
    mock_job_profile = JobProfile(
        title="Senior Python Engineer",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker", "AWS"],
        experience_required=3.0,
        education="Bachelor's degree in Computer Science",
        responsibilities=["Develop APIs", "Manage databases"],
    )
    monkeypatch.setattr("app.services.job_service.extract_job_profile", lambda *args, **kwargs: mock_job_profile)

    payload = {"description": "We are seeking a Senior Python Engineer with 3+ years experience..."}
    response = client.post("/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] > 0
    assert data["title"] == "Senior Python Engineer"
    assert data["required_skills"] == ["Python", "FastAPI"]
    assert data["experience_required"] == 3.0

    # Verify DB persistence
    db = TestingSessionLocal()
    job = db.query(Job).filter(Job.id == data["job_id"]).first()
    assert job is not None
    assert job.title == "Senior Python Engineer"
    db.close()


def test_post_jobs_empty_description():
    """Test POST /jobs rejects empty description string with 400 validation error."""
    response = client.post("/jobs", json={"description": ""})
    assert response.status_code in (400, 422)


# --- 3. POST /matches Tests & 503 Semantic Failure ---

def test_post_matches_successful(monkeypatch):
    """Test POST /matches evaluates candidate against job and persists match result."""
    # Seed DB with candidate and job
    db = TestingSessionLocal()
    cand = Candidate(name="Bob", resume_filename="bob.pdf", resume_text="Bob resume")
    job = Job(title="Backend Dev", description="Backend job description requiring Python")
    db.add_all([cand, job])
    db.commit()
    cand_id, job_id = cand.id, job.id
    db.close()

    mock_sem = SemanticMatchResult(
        semantic_score=80.0,
        strengths=["Strong backend domain fit"],
        gaps=[],
        justification="Relevant experience."
    )
    monkeypatch.setattr("app.services.match_service.evaluate_semantic_match", lambda *args, **kwargs: mock_sem)

    response = client.post("/matches", json={"candidate_id": cand_id, "job_id": job_id})

    assert response.status_code == 200
    data = response.json()
    assert data["candidate_id"] == cand_id
    assert data["job_id"] == job_id
    assert data["score_breakdown"]["semantic_score"] == 80.0

    # Verify DB match record persistence
    db = TestingSessionLocal()
    match = db.query(Match).filter(Match.candidate_id == cand_id, Match.job_id == job_id).first()
    assert match is not None
    assert match.semantic_score == 80.0
    db.close()


def test_post_matches_semantic_failure_returns_503_and_no_db_write(monkeypatch):
    """Test POST /matches returns 503 and writes NO match record when semantic evaluation fails."""
    db = TestingSessionLocal()
    cand = Candidate(name="Alice", resume_filename="alice.pdf", resume_text="Alice resume")
    job = Job(title="Dev", description="Job description")
    db.add_all([cand, job])
    db.commit()
    cand_id, job_id = cand.id, job.id
    db.close()

    def raise_llm_error(*args, **kwargs):
        raise LLMServiceError("Ollama connection refused")

    monkeypatch.setattr("app.services.match_service.evaluate_semantic_match", raise_llm_error)

    response = client.post("/matches", json={"candidate_id": cand_id, "job_id": job_id})

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()

    # CRITICAL CHECK: Verify NO Match record was written to the database!
    db = TestingSessionLocal()
    match_count = db.query(Match).filter(Match.candidate_id == cand_id, Match.job_id == job_id).count()
    assert match_count == 0, "Match record was unexpectedly persisted during semantic 503 failure!"
    db.close()


def test_post_matches_candidate_or_job_not_found():
    """Test POST /matches returns 404 when candidate or job ID does not exist."""
    res1 = client.post("/matches", json={"candidate_id": 999, "job_id": 1})
    assert res1.status_code == 404

    db = TestingSessionLocal()
    cand = Candidate(name="Dave")
    db.add(cand)
    db.commit()
    cand_id = cand.id
    db.close()

    res2 = client.post("/matches", json={"candidate_id": cand_id, "job_id": 999})
    assert res2.status_code == 404


def test_post_matches_duplicate_upsert(monkeypatch):
    """Test repeated POST /matches for same candidate_id + job_id updates existing Match record."""
    db = TestingSessionLocal()
    cand = Candidate(name="Eva")
    job = Job(title="Fullstack", description="Fullstack role")
    db.add_all([cand, job])
    db.commit()
    cand_id, job_id = cand.id, job.id
    db.close()

    mock_sem1 = SemanticMatchResult(semantic_score=60.0, justification="First match")
    monkeypatch.setattr("app.services.match_service.evaluate_semantic_match", lambda *args, **kwargs: mock_sem1)
    res1 = client.post("/matches", json={"candidate_id": cand_id, "job_id": job_id})
    assert res1.status_code == 200

    db = TestingSessionLocal()
    assert db.query(Match).filter(Match.candidate_id == cand_id, Match.job_id == job_id).count() == 1
    db.close()

    # Execute second match evaluation with updated semantic score
    mock_sem2 = SemanticMatchResult(semantic_score=90.0, justification="Second updated match")
    monkeypatch.setattr("app.services.match_service.evaluate_semantic_match", lambda *args, **kwargs: mock_sem2)
    res2 = client.post("/matches", json={"candidate_id": cand_id, "job_id": job_id})
    assert res2.status_code == 200

    db = TestingSessionLocal()
    # Confirm exact 1 match record exists (upserted, not duplicated)
    matches = db.query(Match).filter(Match.candidate_id == cand_id, Match.job_id == job_id).all()
    assert len(matches) == 1
    assert matches[0].semantic_score == 90.0
    assert "Second updated match" in matches[0].justification
    db.close()


# --- 4. GET /matches/{id} Tests ---

def test_get_match_by_id_success():
    """Test GET /matches/{id} retrieves match evaluation by ID."""
    db = TestingSessionLocal()
    cand = Candidate(name="Frank")
    job = Job(title="ML Engineer", description="ML Engineer role")
    db.add_all([cand, job])
    db.flush()

    match_orm = Match(
        candidate_id=cand.id,
        job_id=job.id,
        skill_score=100.0,
        experience_score=100.0,
        education_score=100.0,
        semantic_score=80.0,
        final_score=97.0,
        status="Strong Match",
        justification="Great match.",
    )
    db.add(match_orm)
    db.commit()
    match_id = match_orm.id
    db.close()

    response = client.get(f"/matches/{match_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["candidate_id"] > 0
    assert data["score_breakdown"]["final_score"] == 97.0
    assert data["status"] == "Strong Match"


def test_get_match_by_id_not_found():
    """Test GET /matches/{id} returns 404 when match ID does not exist."""
    response = client.get("/matches/9999")
    assert response.status_code == 404


# --- 5. GET /jobs/{id}/shortlist Tests & Deterministic Ranking ---

def test_get_job_shortlist_deterministic_ranking():
    """Test GET /jobs/{job_id}/shortlist sorts candidates by final_score DESC, candidate_id ASC tie-breaker."""
    db = TestingSessionLocal()
    job = Job(title="DevOps Lead", description="DevOps role requiring Kubernetes and CI/CD")
    c1 = Candidate(id=10, name="Alpha")
    c2 = Candidate(id=20, name="Beta")
    c3 = Candidate(id=30, name="Gamma")
    db.add_all([job, c1, c2, c3])
    db.flush()

    c1_id, c2_id, c3_id = c1.id, c2.id, c3.id

    # c1 score: 85.0
    m1 = Match(candidate_id=c1_id, job_id=job.id, final_score=85.0, status="Strong Match")
    # c2 score: 95.0 (Highest)
    m2 = Match(candidate_id=c2_id, job_id=job.id, final_score=95.0, status="Strong Match")
    # c3 score: 85.0 (Tied with c1, but candidate_id 30 > 10)
    m3 = Match(candidate_id=c3_id, job_id=job.id, final_score=85.0, status="Strong Match")
    db.add_all([m1, m2, m3])
    db.commit()
    job_id = job.id
    db.close()

    response = client.get(f"/jobs/{job_id}/shortlist")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    candidates = data["candidates"]
    assert len(candidates) == 3

    # Order must be: c2 (95.0, id=20), c1 (85.0, id=10), c3 (85.0, id=30)
    assert candidates[0]["candidate_id"] == c2_id
    assert candidates[0]["final_score"] == 95.0

    assert candidates[1]["candidate_id"] == c1_id
    assert candidates[1]["final_score"] == 85.0

    assert candidates[2]["candidate_id"] == c3_id
    assert candidates[2]["final_score"] == 85.0


def test_get_job_shortlist_not_found():
    """Test GET /jobs/{job_id}/shortlist returns 404 when job does not exist."""
    response = client.get("/jobs/9999/shortlist")
    assert response.status_code == 404
