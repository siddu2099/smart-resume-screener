import re
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



def _clean_skills(skills: list[str]) -> list[str]:
    """Post-process extracted skill lists to ensure atomic, concise technical skills."""
    if not skills or not isinstance(skills, list):
        return []

    cleaned: list[str] = []
    prose_patterns = [
        r'^(?:understanding\s+(?:and/or|or)?\s*experience\s+(?:of|in)\s+)',
        r'^(?:understanding\s+of\s+(?:one/more\s+)?(?:programming\s+languages|data\s+analytics\s+or\s+databases|databases)?\s*(?:such\s+as)?\s*)',
        r'^(?:experience\s+(?:of|in|with)\s+)',
        r'^(?:working\s+knowledge\s+of\s+)',
        r'^(?:knowledge\s+of\s+)',
        r'^(?:hands-on\s+experience\s+with\s+)',
        r'^(?:ability\s+to\s+)',
        r'^(?:such\s+as\s+)',
    ]

    for item in skills:
        if not item or not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue

        for pattern in prose_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()

        preserved_slash_terms = {'ci/cd', 'tcp/ip', 'i/o', 'b2b/b2c', 'a/b'}
        if '/' in text and text.lower() not in preserved_slash_terms and not re.search(r'(and|or|in|of|for|with)', text, re.IGNORECASE):
            parts = [p.strip() for p in text.split('/') if p.strip()]
            for p in parts:
                if p and p not in cleaned:
                    cleaned.append(p)
        elif text.lower().startswith('software development'):
            if ' and ' in text.lower():
                subparts = [p.strip() for p in re.split(r'\s+and\s+', text, flags=re.IGNORECASE) if p.strip()]
                for sp in subparts:
                    if sp and sp not in cleaned:
                        cleaned.append(sp.title())
            else:
                if text not in cleaned:
                    cleaned.append(text)
        else:
            if text and text not in cleaned:
                cleaned.append(text)

    return cleaned


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

    if isinstance(parsed_data, dict):
        if "required_skills" in parsed_data and isinstance(parsed_data["required_skills"], list):
            parsed_data["required_skills"] = _clean_skills(parsed_data["required_skills"])
        if "preferred_skills" in parsed_data and isinstance(parsed_data["preferred_skills"], list):
            parsed_data["preferred_skills"] = _clean_skills(parsed_data["preferred_skills"])

    try:
        profile = JobProfile.model_validate(parsed_data)
    except ValidationError as err:
        logger.error("JobProfile Pydantic validation failed: %s", err)
        raise JobParsingError(
            f"LLM JSON output failed JobProfile schema validation: {err}"
        ) from err

    return profile
