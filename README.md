# Smart Resume Screener

## Overview

The Smart Resume Screener is an intelligent academic application designed to automate candidate resume screening and evaluation against job descriptions. It leverages deterministic PDF text extraction, structured information extraction, Pydantic validation, database persistence, and LLM-driven semantic matching to deliver candidate match scoring and ranking.

## Architecture

The end-to-end application pipeline follows a multi-stage flow:

```text
Resume PDF
    ↓
PDF Extraction (PyMuPDF)
    ↓
Resume LLM Extraction (Ollama / qwen2.5:7b)
    ↓
CandidateProfile Schema
    ↓
Database Persistence (SQLite / SQLAlchemy)

Job Description
    ↓
Job LLM Extraction (Ollama / qwen2.5:7b)
    ↓
JobProfile Schema
    ↓
Database Persistence (SQLite / SQLAlchemy)

Candidate + Job
    ↓
Deterministic Skill / Experience / Education Matching
    +
LLM Semantic Alignment Evaluation
    ↓
Deterministic Score Fusion & Status Classification
    ↓
MatchResult Schema
    ↓
Database Persistence & Shortlist Ranking
```

## Technology Stack

- **Python**: 3.11+
- **API Framework**: FastAPI
- **Data Validation**: Pydantic v2
- **ORM / Database**: SQLAlchemy 2.x & SQLite
- **PDF Extraction**: PyMuPDF (`fitz`)
- **LLM Engine**: Ollama (`qwen2.5:7b`)
- **Frontend**: Streamlit
- **Testing**: pytest & `httpx`

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
├── prompts/                # LLM extraction & matching prompt templates
│   ├── resume_extraction.txt
│   ├── job_extraction.txt
│   └── semantic_matching.txt
│
├── frontend/               # Streamlit dashboard interface
│   └── dashboard.py        # Streamlit UI
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
    └── test_phase9_integration.py # End-to-end API integration tests
```

## REST API Endpoints

- `GET /health`: Basic health check endpoint.
- `POST /resumes`: Multipart PDF resume upload; validates PDF, extracts structured candidate data, and persists candidate record.
- `POST /jobs`: Ingest raw job description text; extracts structured job posting data and persists job record.
- `POST /matches`: Evaluate candidate against job using deterministic matching and LLM semantic alignment. Fuses scores and upserts match evaluation record. Returns `503 Service Unavailable` without writing DB records if semantic evaluation fails.
- `GET /matches/{match_id}`: Retrieve persisted candidate-job match evaluation by match ID.
- `GET /jobs/{job_id}/shortlist`: Retrieve ranked candidate shortlist for job posting, sorted deterministically by `final_score` DESC and `candidate_id` ASC as tie-breaker.

## How to Run

### 1. Run Automated Test Suite (pytest)
```powershell
.venv\Scripts\python -m pytest
```

### 2. Start Local Ollama LLM Server
Ensure Ollama is installed and run:
```powershell
ollama serve
ollama pull qwen2.5:7b
```

### 3. Start FastAPI Server
```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```
Interactive API documentation will be available at `http://localhost:8000/docs`.

## Deterministic Matching & LLM Semantic Score Fusion (Phase 8 & 9)

- **Skill Score**: `0.80 * required_score + 0.20 * preferred_score` if preferred skills exist; `required_score` if preferred skills are absent.
- **Experience Score**: `(candidate_years / required_years) * 100` (conservative parsing of explicit numeric/date durations; overlapping/contiguous date ranges merged).
- **Education Score**: Binary `100.0` if degree matches degree/field keywords or requirement is unstated/empty; `0.0` otherwise (institution name excluded).
- **LLM Semantic Score**: Evaluates candidate experience relevance and transferable skills (`prompts/semantic_matching.txt`).
- **Deterministic Score Fusion**:
  $$\text{final\_score} = 0.50 \times \text{skill\_score} + 0.25 \times \text{experience\_score} + 0.10 \times \text{education\_score} + 0.15 \times \text{semantic\_score}$$
- **Status Classification**: Deterministically enforced by required skill coverage ($\ge 80\%$ for `STRONG`, $\ge 50\%$ for `POTENTIAL`). High semantic scores cannot compensate for missing required skills.

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
