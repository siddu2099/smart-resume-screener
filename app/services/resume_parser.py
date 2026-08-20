"""Structured resume extraction service using LLM output and Pydantic validation."""

import json
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError

from app.schemas.resume import CandidateProfile
from app.services.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


class ResumeParsingError(Exception):
    """Custom exception raised when resume LLM parsing or Pydantic validation fails."""

    pass


def _clean_json_response(raw_response: str) -> str:
    """Clean raw LLM string output by removing surrounding markdown code fences.

    Args:
        raw_response: Raw string output returned by LLM.

    Returns:
        Cleaned JSON string ready for json.loads parsing.
    """
    cleaned = raw_response.strip()

    # Remove markdown code fence if present
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop first line if it contains opening fence (``` or ```json)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Drop last line if it contains closing fence (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned


def extract_resume_profile(
    resume_text: str,
    llm_service: Optional[LLMService] = None,
    prompt_path: Optional[Union[str, Path]] = None,
) -> CandidateProfile:
    """Extract structured CandidateProfile from normalized resume text using LLM.

    Args:
        resume_text: Normalized plain text extracted from resume.
        llm_service: Optional LLMService instance (defaults to new LLMService()).
        prompt_path: Optional path to resume extraction prompt template file.

    Returns:
        Validated CandidateProfile instance.

    Raises:
        ResumeParsingError: If resume text is empty, prompt file missing, JSON parsing fails,
                            or Pydantic validation fails.
        LLMServiceError: If LLM service call fails.
    """
    if not resume_text or not resume_text.strip():
        raise ResumeParsingError("Resume text cannot be empty or whitespace only")

    # Resolve prompt template path relative to module location if not specified
    if prompt_path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        prompt_file = project_root / "prompts" / "resume_extraction.txt"
    else:
        prompt_file = Path(prompt_path)

    if not prompt_file.is_file():
        raise ResumeParsingError(f"Prompt template file not found at: {prompt_file}")

    try:
        template_text = prompt_file.read_text(encoding="utf-8")
    except Exception as err:
        raise ResumeParsingError(f"Failed to read prompt template file: {err}") from err

    prompt = template_text.replace("{resume_text}", resume_text)

    service = llm_service or LLMService()

    try:
        raw_output = service.generate_completion(prompt, format_json=True)
    except LLMServiceError:
        raise
    except Exception as err:
        raise ResumeParsingError(f"Unexpected LLM generation error: {err}") from err

    cleaned_json_str = _clean_json_response(raw_output)

    try:
        parsed_data = json.loads(cleaned_json_str)
    except json.JSONDecodeError as err:
        logger.error("LLM JSON parsing failed: %s", err)
        raise ResumeParsingError(f"Failed to parse LLM response as valid JSON: {err}") from err

    if not isinstance(parsed_data, dict):
        raise ResumeParsingError(
            f"Expected JSON object dictionary from LLM, got {type(parsed_data).__name__}"
        )

    try:
        profile = CandidateProfile.model_validate(parsed_data)
    except ValidationError as err:
        logger.error("CandidateProfile Pydantic validation failed: %s", err)
        raise ResumeParsingError(
            f"LLM JSON output failed CandidateProfile schema validation: {err}"
        ) from err

    return profile
