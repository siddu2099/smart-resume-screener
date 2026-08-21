# Smart Resume Screener

## Overview

The Smart Resume Screener is an intelligent academic application designed to automate candidate resume screening and evaluation against job descriptions. It leverages deterministic PDF text extraction, structured information extraction, Pydantic validation, database persistence, LLM-driven semantic matching, FastAPI REST endpoints, and a Streamlit dashboard interface to deliver candidate match scoring and ranking.

## Architecture

The end-to-end application pipeline follows a multi-stage flow:

```text
Resume PDF Upload (Streamlit UI / POST /resumes)
    ↓
PDF Extraction (PyMuPDF)
    ↓
Resume LLM Extraction (Ollama / qwen2.5:7b)
    ↓
CandidateProfile Schema
    ↓
Database Persistence (SQLite / SQLAlchemy)

Job Description Input (Streamlit UI / POST /jobs)
    ↓
Job LLM Extraction (Ollama / qwen2.5:7b)
    ↓
JobProfile Schema
    ↓
Database Persistence (SQLite / SQLAlchemy)

Candidate + Job Match Request (Streamlit UI / POST /matches)
    ↓
Deterministic Skill / Experience / Education Matching
    +
LLM Semantic Alignment Evaluation
    ↓
Deterministic Score Fusion & Status Classification
    ↓
MatchResult Schema
    ↓
Database Persistence & Shortlist Ranking (GET /jobs/{job_id}/shortlist)
```

## Technology Stack

- **Python**: 3.11+
- **API Framework**: FastAPI
- **Data Validation**: Pydantic v2
- **ORM / Database**: SQLAlchemy 2.x & SQLite
- **PDF Extraction**: PyMuPDF (`fitz`)
- **LLM Engine**: Ollama (`qwen2.5:7b`)
- **HTTP Client**: `httpx`
- **Frontend**: Streamlit
- **Testing**: pytest

## Project Structure

```text
smart-resume-screener/
│
├── README.md               # Project documentation
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables configuration template
│
├── app/                    # Main application package
│   ├── __init__.py
│   ├── main.py             # FastAPI entry point & lifespan setup
│   │
│   ├── api/                # API router modules
│   │   ├── __init__.py
│   │   ├── resumes.py      # Resume ingestion endpoint (POST /resumes)
│   │   ├── jobs.py         # Job description endpoint (POST /jobs)
│   │   └── matching.py     # Matching & shortlist endpoints (POST /matches, GET /shortlist)
│   │
│   ├── schemas/            # Pydantic data contracts
│   │   ├── __init__.py
│   │   ├── resume.py       # Candidate profile & API schemas
│   │   ├── job.py          # Job profile & API schemas
│   │   └── matching.py     # Match result & Shortlist schemas
│   │
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── candidate.py    # Candidate, Skill, Experience, Education models
│   │   ├── job.py          # Job posting model
│   │   └── match.py        # Candidate-Job Match model
│   │
│   ├── services/           # Core business logic services
│   │   ├── __init__.py
│   │   ├── pdf_parser.py   # PyMuPDF text parser
│   │   ├── resume_parser.py# Structured resume extraction service
│   │   ├── job_parser.py   # Job description extraction service
│   │   ├── llm_service.py  # Ollama LLM integration wrapper
│   │   ├── matcher.py      # Deterministic scoring & fusion engine
│   │   ├── semantic_matcher.py # LLM semantic matching service
│   │   ├── candidate_service.py # Candidate orchestration service
│   │   ├── job_service.py  # Job orchestration service
│   │   └── match_service.py# Match orchestration & shortlist service
│   │
│   └── database/           # Database configuration
│       ├── __init__.py
│       └── database.py     # Engine, session, and init_db setup
│
├── frontend/               # Streamlit frontend package
│   ├── __init__.py
│   ├── api_client.py       # Typed REST API client wrapper (httpx)
│   └── dashboard.py        # Multi-tab Streamlit dashboard UI
│
├── prompts/                # LLM extraction & matching prompt templates
│   ├── resume_extraction.txt
│   ├── job_extraction.txt
│   └── semantic_matching.txt
│
└── tests/                  # Automated test suite
    ├── __init__.py
    ├── test_api.py         # Health check tests
    ├── test_pdf_parser.py  # PDF parser unit tests
    ├── test_resume_parser.py # Resume extraction unit tests
    ├── test_job_parser.py  # Job extraction unit tests
    ├── test_llm_service.py # LLM service unit tests
    ├── test_matching.py    # Deterministic matcher tests
    ├── test_semantic_matcher.py # Semantic matcher unit tests
    ├── test_phase9_integration.py # End-to-end API integration tests
    └── test_api_client.py  # Frontend API client tests
```

## How to Run

### 1. Run Automated Test Suite (pytest)
```powershell
.venv\Scripts\python -m pytest
```

### 2. Local End-to-End Execution Workflow

#### Terminal 1 — Start Local Ollama LLM Server
Ensure Ollama is installed and run:
```powershell
ollama serve
ollama pull qwen2.5:7b
```

#### Terminal 2 — Start FastAPI Backend
```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```
Interactive API documentation will be available at `http://127.0.0.1:8000/docs`.

#### Terminal 3 — Start Streamlit Dashboard UI
```powershell
# Optional: Set custom API base URL if backend runs on a different port/host
# $env:API_BASE_URL="http://127.0.0.1:8000"

.venv\Scripts\python -m streamlit run frontend/dashboard.py
```
The Streamlit dashboard will open automatically in your browser at `http://localhost:8501`.

## Streamlit Dashboard Workflow

1. **📤 Resume Upload**: Upload a candidate PDF resume. The UI sends the file to `POST /resumes` and displays candidate details, skills, experience, and education.
2. **💼 Job Posting**: Paste a job description string. The UI sends text to `POST /jobs` and displays required vs. preferred skills, experience requirements, and responsibilities.
3. **⚖️ Match Evaluation**: Input Candidate ID and Job ID. The UI calls `POST /matches` and displays score metrics, qualification status badge (Strong/Potential/Weak), matched/missing required skills, strengths, gaps, and evaluation justification.
4. **🏆 Shortlist Dashboard**: Input Job ID. The UI calls `GET /jobs/{job_id}/shortlist` and displays candidate rankings strictly in backend-authoritative order.

## REST API Endpoints

- `GET /health`: Basic health check endpoint.
- `POST /resumes`: Multipart PDF resume upload; validates PDF, extracts structured candidate data, and persists candidate record.
- `POST /jobs`: Ingest raw job description text; extracts structured job posting data and persists job record.
- `POST /matches`: Evaluate candidate against job using deterministic matching and LLM semantic alignment. Fuses scores and upserts match evaluation record. Returns `503 Service Unavailable` without writing DB records if semantic evaluation fails.
- `GET /matches/{match_id}`: Retrieve persisted candidate-job match evaluation by match ID.
- `GET /jobs/{job_id}/shortlist`: Retrieve ranked candidate shortlist for job posting, sorted deterministically by `final_score` DESC and `candidate_id` ASC as tie-breaker.

## Development Status

- **Phase 1 — Project Initialization**: Completed
- **Phase 2 — Database Models & Schemas**: Completed
- **Phase 3 — PDF Extraction & Parsers**: Completed
- **Phase 4 — Pydantic Domain Schemas**: Completed
- **Phase 5 — LLM Resume Extraction**: Completed
- **Phase 6 — LLM Job Description Extraction**: Completed
- **Phase 7 — Deterministic Candidate-Job Matching Engine**: Completed
- **Phase 8 — LLM Semantic Analysis & Score Fusion**: Completed
- **Phase 9 — Application API, Persistence Integration & Shortlisting**: Completed
- **Phase 10 — Streamlit Dashboard & End-to-End UI**: Completed
