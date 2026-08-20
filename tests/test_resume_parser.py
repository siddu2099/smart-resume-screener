"""Unit tests for structured resume parser service."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.schemas.resume import CandidateProfile
from app.services.llm_service import LLMService, LLMServiceError
from app.services.resume_parser import ResumeParsingError, _clean_json_response, extract_resume_profile


def test_clean_json_response_raw_and_markdown():
    """Test cleaning raw JSON string and markdown code-fenced JSON output."""
    raw = '{"name": "Alice"}'
    assert _clean_json_response(raw) == '{"name": "Alice"}'

    fenced = '```json\n{"name": "Bob"}\n```'
    assert _clean_json_response(fenced) == '{"name": "Bob"}'

    plain_fence = '```\n{"name": "Charlie"}\n```'
    assert _clean_json_response(plain_fence) == '{"name": "Charlie"}'


def test_extract_resume_profile_complete():
    """Test complete candidate profile extraction with mocked LLMService."""
    llm_payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0199",
        "skills": ["Python", "FastAPI", "SQL", "C++", "CI/CD"],
        "experience": [
            {
                "company": "Acme Corp",
                "role": "Senior Engineer",
                "duration": "2022 - Present",
                "description": "Led backend API microservices development.",
            }
        ],
        "education": [
            {
                "degree": "B.Tech Computer Science",
                "institution": "State University",
                "year": "2022",
            }
        ],
    }

    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps(llm_payload)

    resume_text = "Jane Doe\nSoftware Engineer\nSkills: Python, FastAPI, C++, CI/CD"
    profile = extract_resume_profile(resume_text, llm_service=mock_service)

    assert isinstance(profile, CandidateProfile)
    assert profile.name == "Jane Doe"
    assert profile.email == "jane@example.com"
    assert "C++" in profile.skills
    assert "CI/CD" in profile.skills
    assert len(profile.experience) == 1
    assert profile.experience[0].company == "Acme Corp"
    assert len(profile.education) == 1
    assert profile.education[0].year == "2022"


def test_extract_resume_profile_missing_optionals():
    """Test candidate extraction handling missing optionals (null and empty lists)."""
    llm_payload = {
        "name": "Minimal Candidate",
        "email": None,
        "phone": None,
        "skills": ["Python"],
        "experience": [],
        "education": [],
    }

    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps(llm_payload)

    profile = extract_resume_profile("Minimal Candidate resume text", llm_service=mock_service)
    assert profile.name == "Minimal Candidate"
    assert profile.email is None
    assert profile.phone is None
    assert profile.skills == ["Python"]
    assert profile.experience == []
    assert profile.education == []


def test_extract_resume_profile_markdown_code_fence():
    """Test accepting markdown code-fenced JSON from LLM."""
    llm_payload = {"name": "Fenced Candidate", "skills": ["Docker"]}
    fenced_output = f"```json\n{json.dumps(llm_payload)}\n```"

    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = fenced_output

    profile = extract_resume_profile("Fenced Candidate text", llm_service=mock_service)
    assert profile.name == "Fenced Candidate"
    assert profile.skills == ["Docker"]


def test_extract_resume_profile_empty_resume_text():
    """Test that passing empty or whitespace resume text raises ResumeParsingError."""
    with pytest.raises(ResumeParsingError, match="Resume text cannot be empty"):
        extract_resume_profile("   ")


def test_extract_resume_profile_malformed_json():
    """Test that malformed JSON response from LLM raises ResumeParsingError."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = '{"name": "Bad JSON", "skills": ['

    with pytest.raises(ResumeParsingError, match="Failed to parse LLM response as valid JSON"):
        extract_resume_profile("Resume text", llm_service=mock_service)


def test_extract_resume_profile_invalid_pydantic_schema():
    """Test that valid JSON with invalid field type raises ResumeParsingError."""
    llm_payload = {"name": "Test", "skills": "Not A List"}

    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps(llm_payload)

    with pytest.raises(ResumeParsingError, match="failed CandidateProfile schema validation"):
        extract_resume_profile("Resume text", llm_service=mock_service)


def test_extract_resume_profile_llm_service_error_passthrough():
    """Test that LLMServiceError exceptions pass through cleanly."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.side_effect = LLMServiceError("Ollama service unavailable")

    with pytest.raises(LLMServiceError, match="unavailable"):
        extract_resume_profile("Resume text", llm_service=mock_service)


def test_prompt_template_file_loaded():
    """Test that the prompt template file is loaded and formatted correctly."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps({"name": "Loaded Test"})

    extract_resume_profile("UniqueResumeContent12345", llm_service=mock_service)

    mock_service.generate_completion.assert_called_once()
    prompt_arg = mock_service.generate_completion.call_args[0][0]
    assert "--- BEGIN RESUME DATA ---" in prompt_arg
    assert "UniqueResumeContent12345" in prompt_arg
    assert "--- END RESUME DATA ---" in prompt_arg


def test_technical_skills_preservation():
    """Test that technical skill terms such as C++, C#, .NET, Node.js, and CI/CD are preserved."""
    skills = ["C++", "C#", ".NET", "Node.js", "React.js", "AWS", "CI/CD"]
    llm_payload = {"name": "Tech Skill Candidate", "skills": skills}

    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps(llm_payload)

    profile = extract_resume_profile("Technical skills text", llm_service=mock_service)
    assert profile.skills == skills


def test_no_database_side_effects_on_parsing():
    """Test that resume parsing creates no database files in the workspace root."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.generate_completion.return_value = json.dumps({"name": "No DB Test"})

    extract_resume_profile("No DB text", llm_service=mock_service)

    root_db = Path("resume_screener.db")
    assert not root_db.exists(), "Resume parsing unexpectedly created a database file!"
