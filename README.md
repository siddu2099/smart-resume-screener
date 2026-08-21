# Smart Resume Screener

## Overview

The Smart Resume Screener is an intelligent academic application designed to automate candidate resume screening and evaluation against job descriptions. It leverages deterministic PDF text extraction, structured information extraction, Pydantic validation, database persistence, and LLM-driven semantic matching to deliver candidate match scoring and ranking.

## Planned Architecture

The application pipeline follows a multi-stage flow:

```text
Resume PDF / Text
       ↓
Deterministic Text Extraction (PyMuPDF)
       ↓
LLM Structured Extraction (Ollama)
       ↓
Pydantic Validation
       ↓
Database Storage (SQLite / SQLAlchemy)
       ↓
Deterministic Matching + LLM Semantic Analysis
       ↓
Weighted Final Score & Ranking
       ↓
User Interfaces (FastAPI REST API / Streamlit Dashboard)
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
│   ├── main.py             # FastAPI entry point
│   │
│   ├── api/                # API router modules
│   │   ├── __init__.py
│   │   ├── resumes.py      # Resume ingestion endpoints (TODO)
│   │   ├── jobs.py         # Job description endpoints (TODO)
│   │   └── matching.py     # Resume-Job matching endpoints (TODO)
│   │
│   ├── schemas/            # Pydantic data schemas
│   │   ├── __init__.py
│   │   ├── resume.py       # Structured resume schema (TODO)
│   │   ├── job.py          # Structured job description schema (TODO)
│   │   └── matching.py     # Match result schema (TODO)
│   │
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── candidate.py    # Candidate/Resume DB model (TODO)
│   │   ├── job.py          # Job posting DB model (TODO)
│   │   └── match.py        # Candidate Match DB model (TODO)
│   │
│   ├── services/           # Core business logic services
│   │   ├── __init__.py
│   │   ├── pdf_parser.py   # PyMuPDF text parser (TODO)
│   │   ├── resume_parser.py# Structured resume extraction service (TODO)
│   │   ├── job_parser.py   # Job description extraction service (TODO)
│   │   ├── llm_service.py  # Ollama LLM integration (TODO)
│   │   └── matcher.py      # Scoring & ranking engine (TODO)
│   │
│   └── database/           # Database configuration
│       ├── __init__.py
│       └── database.py     # Engine and session setup (TODO)
│
├── prompts/                # LLM extraction & matching prompt templates
│   ├── resume_extraction.txt
│   ├── job_extraction.txt
│   └── semantic_matching.txt
│
├── frontend/               # Streamlit dashboard interface
│   └── dashboard.py        # Streamlit UI (TODO)
│
└── tests/                  # Automated test suite
    ├── __init__.py
    ├── test_api.py         # Health check & API integration tests
    ├── test_pdf_parser.py  # PDF parser unit tests (TODO)
    └── test_matching.py    # Matcher service tests (TODO)
```

## Deterministic Matching Engine (Phase 7.1)

The candidate-job matching engine operates 100% deterministically without LLM or database dependencies:

- **Skill Score**:
  - If preferred skills exist: `skill_score = 0.80 * required_score + 0.20 * preferred_score`
  - Otherwise (no preferred skills in job): `skill_score = required_score` (preferred score is `0.0`, candidate is not penalized)
- **Experience Score**:
  - `(candidate_years / required_years) * 100` (clamped to 100; returns 100.0 if required experience is `None` or `0`).
  - Conservative experience parsing: recognizes explicit numeric/date durations (`"YYYY - YYYY"`, `"YYYY - Present"`, `"X years"`, `"X months"`).
  - Year-only ranges use an approximate calendar-year model (e.g., `"2022 - 2024"` ≈ 2.0 yrs).
  - Overlapping, contiguous, duplicate, and Present date ranges are merged before calculating total experience.
  - Vague language (e.g., `"strong experience"`, `"several years"`) contributes `0` parsed years.
- **Education Score**: Binary `100.0` if candidate degree matches required degree/field keywords, `100.0` if job requirement is unstated/empty, `0.0` otherwise (institution name is excluded from field evaluation).
- **Deterministic Final Score**: `0.60 * skill_score + 0.30 * experience_score + 0.10 * education_score`
- **Status Rules**:
  - `STRONG`: `final_score >= 80.0` AND `required_skill_coverage >= 80%`
  - `POTENTIAL`: `final_score >= 60.0` AND `required_skill_coverage >= 50%`
  - `WEAK`: Otherwise
- **Note**: `semantic_score` is set to `0.0` baseline; LLM semantic matching will be implemented in Phase 8.

## Development Status

- **Phase 1 — Project Initialization**: Completed
- **Phase 2 — Database Models & Schemas**: Completed
- **Phase 3 — PDF Extraction & Parsers**: Completed
- **Phase 4 — Pydantic Domain Schemas**: Completed
- **Phase 5 — LLM Resume Extraction**: Completed
- **Phase 6 — LLM Job Description Extraction**: Completed
- **Phase 7 — Deterministic Candidate-Job Matching Engine**: Completed
- **Phase 8 — LLM Semantic Analysis & Shortlist Dashboard**: Pending
