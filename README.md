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

## Development Status

- **Phase 1 — Project Initialization**: Completed
- **Phase 2 — Database Models & Schemas**: Completed
- **Phase 3 — PDF Extraction & Parsers**: Completed
- **Phase 4 — LLM Integration & Matching**: Pending
- **Phase 5 — API & Streamlit Dashboard**: Pending
