# Smart AI Resume Screener & Candidate Matcher

> **Production-Grade Automated Candidate Evaluation & Shortlisting System**  
> Powered by **FastAPI**, **PostgreSQL / SQLAlchemy 2.x**, **PyMuPDF**, **Ollama (`qwen2.5:7b`)**, and **Streamlit**.

---

## 📌 Overview

The **Smart AI Resume Screener & Candidate Matcher** is an end-to-end intelligent recruitment engine designed to automate resume parsing, job description analysis, candidate-to-job matching, and candidate shortlisting.

It combines **deterministic matching algorithms** (for precise skill, experience, and education validation) with **bounded local LLM semantic analysis** (for deep experience relevance, domain suitability, and qualitative justification).

### Key Highlights
- **Bounded LLM Semantic Analysis**: Deterministic facts strictly override semantic explanations. The LLM can explain facts, but cannot rewrite skill classifications, required coverage ratios, or score thresholds.
- **High-Performance Local Inference**: Integrated with local **Ollama (`qwen2.5:7b`)**, ensuring zero data privacy risk with customizable timeouts and graceful fallback if Ollama is unreachable.
- **Enterprise Database Persistence**: Full **PostgreSQL** support via SQLAlchemy 2.x ORM with auto-fallback to local SQLite (`sqlite:///./resume_screener.db`).
- **Interactive Streamlit Dashboard**: Clean recruiter dashboard providing tabbed navigation for uploading resumes, creating job postings, running match evaluations, and viewing candidate shortlists.
- **Comprehensive Test Suite**: Automated unit and integration tests covering PDF parsing, entity extraction, deterministic matching, score fusion, and API endpoints.

---

## 🏗️ Architecture & Scoring Methodology

```
                   +------------------------+
                   | Candidate Resume (PDF) |
                   +-----------+------------+
                               |
                               v
                       [ PyMuPDF Parser ]
                               |
                               v
                  +------------+------------+
                  |  Candidate Profile      |
                  |  (Skills, Exp, Edu)     |
                  +------------+------------+
                               |
   +---------------------------+---------------------------+
   |                                                       |
   v                                                       v
[ Deterministic Matching Engine ]            [ Bounded LLM Semantic Evaluator ]
 * Skill Score       (50%)                     * Domain Fit & Relevance  (15%)
 * Experience Score  (25%)                     * Qualitative Strengths & Gaps
 * Education Score   (10%)                     * Bounded Rule Guardrails
   |                                                       |
   +---------------------------+---------------------------+
                               |
                               v
                  +------------+------------+
                  |    Score Fusion Engine  |
                  |  final_score (0 - 100%) |
                  +------------+------------+
                               |
                               v
                 +-------------+-------------+
                 | Candidate Status Classifier|
                 |  STRONG / POTENTIAL / WEAK|
                 +-------------+-------------+
                               |
                               v
                   +-----------+------------+
                   | Database & Shortlist API|
                   +------------------------+
```

### 🧮 Score Fusion Formula
Final candidate scores are calculated deterministically across four key pillars:

`Final Score = (0.50 * Skill Score) + (0.25 * Experience Score) + (0.10 * Education Score) + (0.15 * Semantic Score)`

1. **Skill Score (50%)**: Weighted calculation based on 80% Required Skill coverage + 20% Preferred Skill coverage.
2. **Experience Score (25%)**: Calculates candidate total work experience by parsing and merging overlapping calendar date intervals, scored against the job's minimum experience requirement.
3. **Education Score (10%)**: Validates degree levels and field keywords against job prerequisites (100.0 if met, 0.0 otherwise).
4. **Semantic Score (15%)**: Bounded LLM evaluation (0 - 100) focusing on domain alignment, role relevance, and qualitative insights.

### 📊 Candidate Classification Thresholds

| Classification | Score Threshold | Required Skill Coverage | Description |
| :--- | :--- | :--- | :--- |
| **STRONG** | >= 80.0% | >= 80.0% | Exceptional match; strongly recommended for immediate interview. |
| **POTENTIAL** | >= 60.0% | >= 50.0% | Good candidate meeting baseline prerequisites; worth secondary review. |
| **WEAK** | < 60.0% | < 50.0% | Insufficient skill coverage or overall score below hiring threshold. |

*Note: Required skill coverage strictly bounds status classification regardless of the semantic score.*

---

## 📁 Repository Structure

```
resume-screener/
├── app/
│   ├── api/                  # FastAPI REST endpoints
│   │   ├── jobs.py           # Job posting ingestion
│   │   ├── matching.py       # Candidate-job matching & shortlisting
│   │   └── resumes.py        # PDF resume upload & parsing
│   ├── database/             # Database connection & session lifecycle
│   │   └── database.py       # SQLAlchemy engine & Base model initialization
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── candidate.py      # Candidate database schema
│   │   ├── job.py            # Job posting database schema
│   │   └── match.py          # Match evaluation database schema
│   ├── schemas/              # Pydantic v2 request/response schemas
│   │   ├── job.py            # Job profile schemas
│   │   ├── matching.py       # Match request & result schemas
│   │   └── resume.py         # Candidate profile schemas
│   ├── services/             # Core business logic
│   │   ├── candidate_service.py # Candidate PDF persistence & service logic
│   │   ├── job_parser.py     # Job description parser
│   │   ├── job_service.py     # Job persistence service
│   │   ├── llm_service.py     # Local Ollama client with fallback
│   │   ├── match_service.py   # Match persistence & shortlist fetcher
│   │   ├── matcher.py         # Deterministic score fusion engine
│   │   ├── pdf_parser.py     # PyMuPDF text extraction
│   │   ├── resume_parser.py  # Resume profile extractor
│   │   └── semantic_matcher.py # Bounded LLM semantic evaluator
│   └── main.py               # FastAPI entry point & lifespan handler
├── frontend/
│   ├── api_client.py         # ScreenerAPIClient wrapper for REST API
│   └── dashboard.py          # Streamlit UI application
├── prompts/                  # LLM extraction & evaluation prompt templates
├── tests/                    # Unit and integration test suite
├── .env                      # Environment configuration file
├── .gitignore                # Git ignore rules
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🛠️ Tech Stack

- **Backend Framework**: Python 3.10+, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **Frontend UI**: [Streamlit](https://streamlit.io/)
- **Database ORM**: PostgreSQL via [SQLAlchemy 2.x](https://www.sqlalchemy.org/) (`psycopg2`) with auto-fallback to SQLite
- **PDF Parsing**: PyMuPDF (`fitz`)
- **Data Validation**: Pydantic v2
- **AI / LLM Inference**: [Ollama](https://ollama.com/) running `qwen2.5:7b` (with heuristic fallback)
- **Testing**: `pytest`, `httpx`

---

## ⚙️ Configuration & Environment Variables

Copy or edit the `.env` file in the root directory to configure the environment:

```ini
# Database Connection URL (PostgreSQL or SQLite fallback)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/resume_screener

# Ollama LLM Connection Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=120.0

# API Client Settings (Streamlit Frontend)
API_BASE_URL=http://127.0.0.1:8000
API_TIMEOUT=120.0
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+** installed
- **Ollama** (optional, recommended for full semantic evaluation):
  ```bash
  ollama pull qwen2.5:7b
  ```

### 2. Installation
Clone the repository and set up a virtual environment:

```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Backend API
Start the FastAPI server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Documentation (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: `GET http://127.0.0.1:8000/health`

### 4. Run the Streamlit Dashboard
In a separate terminal window:

```bash
streamlit run frontend/dashboard.py
```
- Streamlit Web App: [http://localhost:8501](http://localhost:8501)

---

## 🌐 API Reference

### Resumes (`/resumes`)
- `POST /resumes`: Upload candidate resume (PDF format). Extracts candidate profile and saves to database.

### Jobs (`/jobs`)
- `POST /jobs`: Submit job description text. Extracts job profile (skills, experience, education) and saves to database.

### Matching & Shortlisting (`/matches`)
- `POST /matches`: Match a specific `candidate_id` against a `job_id`. Performs score fusion and persists match evaluation.
- `GET /matches/{match_id}`: Retrieve stored match result details.
- `GET /jobs/{job_id}/shortlist`: Retrieve candidate shortlist for a job, ranked deterministically by `final_score DESC, candidate_id ASC`.

---

## 🧪 Running Tests

Execute the complete pytest suite to verify system integrity:

```bash
pytest -v
```

Tests cover:
- PDF text extraction (`test_pdf_parser.py`)
- Resume & job entity parsing (`test_resume_parser.py`, `test_job_parser.py`)
- Deterministic matcher & score fusion (`test_matching.py`)
- Bounded semantic matcher (`test_semantic_matcher.py`)
- Database ORM operations (`test_database.py`)
- API endpoints & frontend client (`test_api.py`, `test_api_client.py`)
- End-to-end integration workflows (`test_phase9_integration.py`)
## Demo Video

[▶ Watch the 2–3 minute demo](https://drive.google.com/file/d/1teq1q4SWQPyqvcjgF40d2uJ2hcmY1p2v/view?usp=sharing)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
