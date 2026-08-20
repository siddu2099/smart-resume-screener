"""Structured job description extraction service using LLM output and Pydantic validation."""

import json
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError

from app.schemas.job import JobProfile
from app.services.llm_service import LLMService, LLMServiceError
from app.services.resume_parser import _clean_json_response

logger = logging.getLogger(__name__)


class JobParsingError(Exception):
    """Custom exception raised when job description LLM parsing or Pydantic validation fails."""

    pass


def extract_job_profile(
    job_text: str,
    llm_service: Optional[LLMService] = None,
    prompt_path: Optional[Union[str, Path]] = None,
) -> JobProfile:
    """Extract structured JobProfile from raw job description text using LLM.

    Args:
        job_text: Raw or normalized job description text.
        llm_service: Optional LLMService instance (defaults to new LLMService()).
        prompt_path: Optional path to job extraction prompt template file.

    Returns:
        Validated JobProfile instance.

    Raises:
        JobParsingError: If job_text is empty, prompt template missing, JSON parsing fails,
                         or Pydantic validation fails.
        LLMServiceError: If LLM service communication fails.
    """
    if not job_text or not job_text.strip():
        raise JobParsingError("Job description text cannot be empty or whitespace only")

    # Resolve prompt template path relative to module location if not specified
    if prompt_path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        prompt_file = project_root / "prompts" / "job_extraction.txt"
    else:
        prompt_file = Path(prompt_path)

    if not prompt_file.is_file():
        raise JobParsingError(f"Prompt template file not found at: {prompt_file}")

    try:
        template_text = prompt_file.read_text(encoding="utf-8")
    except Exception as err:
        raise JobParsingError(f"Failed to read job extraction prompt template: {err}") from err

    prompt = template_text.replace("{job_text}", job_text)

    service = llm_service or LLMService()

    try:
        raw_output = service.generate_completion(prompt, format_json=True)
    except LLMServiceError:
        raise
    except Exception as err:
        raise JobParsingError(f"Unexpected LLM generation error: {err}") from err

    cleaned_json_str = _clean_json_response(raw_output)

    try:
        parsed_data = json.loads(cleaned_json_str)
    except json.JSONDecodeError as err:
        logger.error("Job LLM JSON parsing failed: %s", err)
        raise JobParsingError(f"Failed to parse LLM response as valid JSON: {err}") from err

    if not isinstance(parsed_data, dict):
        raise JobParsingError(
            f"Expected JSON object dictionary from LLM, got {type(parsed_data).__name__}"
        )

    try:
        profile = JobProfile.model_validate(parsed_data)
    except ValidationError as err:
        logger.error("JobProfile Pydantic validation failed: %s", err)
        raise JobParsingError(
            f"LLM JSON output failed JobProfile schema validation: {err}"
        ) from err

    return profile
