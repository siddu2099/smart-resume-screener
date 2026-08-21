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

## Deterministic Matching & LLM Semantic Score Fusion (Phase 8)

The matching engine integrates deterministic skill, experience, and education analysis with LLM-driven semantic experience alignment:

### 1. Deterministic Evaluation (Phase 7.1 Engine)
- **Skill Score**: `0.80 * required_score + 0.20 * preferred_score` if preferred skills exist; `required_score` if preferred skills are absent.
- **Experience Score**: `(candidate_years / required_years) * 100` (conservative parsing of explicit numeric/date durations; overlapping and contiguous intervals merged).
- **Education Score**: Binary `100.0` if candidate degree matches degree/field keywords or if job requirement is unstated/empty; `0.0` otherwise (institution name excluded).

### 2. LLM Semantic Evaluation (`app/services/semantic_matcher.py`)
- Evaluates candidate experience relevance, domain suitability, and transferable skills using local Ollama LLM (`prompts/semantic_matching.txt`).
- **Prompt Injection Defense**: Treats CandidateProfile and JobProfile strictly as untrusted data.
- **Validation**: All LLM outputs are cleaned of markdown fences and strictly validated via `SemanticMatchResult.model_validate(...)`. Out-of-bounds scores (`<0` or `>100`), malformed JSON, or missing fields raise `SemanticMatchingError`.
- **Hallucination & Contradiction Safeguards**: LLM outputs cannot invent unstated skills/experience or override deterministic required skill facts. Contradictory semantic claims are filtered out during fusion.

### 3. Deterministic Score Fusion Formula
$$\text{final\_score} = 0.50 \times \text{skill\_score} + 0.25 \times \text{experience\_score} + 0.10 \times \text{education\_score} + 0.15 \times \text{semantic\_score}$$
Rounded to 2 decimal places and clamped to $[0.0, 100.0]$.

### 4. Qualification Status Classification
Status classification is 100% deterministic and strictly controlled by required-skill coverage regardless of semantic score:
- **STRONG**: `final_score >= 80.0` AND `required_skill_coverage >= 80%`
- **POTENTIAL**: `final_score >= 60.0` AND `required_skill_coverage >= 50%`
- **WEAK**: Otherwise

## Development Status

- **Phase 1 — Project Initialization**: Completed
- **Phase 2 — Database Models & Schemas**: Completed
- **Phase 3 — PDF Extraction & Parsers**: Completed
- **Phase 4 — Pydantic Domain Schemas**: Completed
- **Phase 5 — LLM Resume Extraction**: Completed
- **Phase 6 — LLM Job Description Extraction**: Completed
- **Phase 7 — Deterministic Candidate-Job Matching Engine**: Completed
- **Phase 8 — LLM Semantic Analysis & Score Fusion**: Completed

