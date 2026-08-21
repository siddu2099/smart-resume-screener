"""LLM-driven semantic candidate-job matching evaluation service."""

import json
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError

from app.schemas.job import JobProfile
from app.schemas.matching import SemanticMatchResult
from app.schemas.resume import CandidateProfile
from app.services.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


class SemanticMatchingError(Exception):
    """Custom exception raised when semantic matching JSON parsing or validation fails."""

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
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned


def evaluate_semantic_match(
    candidate: CandidateProfile,
    job: JobProfile,
    llm_service: Optional[LLMService] = None,
    prompt_path: Optional[Union[str, Path]] = None,
) -> SemanticMatchResult:
    """Evaluate semantic experience alignment between CandidateProfile and JobProfile using LLM.

    Args:
        candidate: CandidateProfile domain schema instance.
        job: JobProfile domain schema instance.
        llm_service: Optional LLMService instance (defaults to new LLMService()).
        prompt_path: Optional path to semantic matching prompt template file.

    Returns:
        Validated SemanticMatchResult domain schema instance.

    Raises:
        SemanticMatchingError: If prompt template is missing, response is empty/invalid JSON,
                               or schema validation fails.
        LLMServiceError: If LLM service call fails.
    """
    # Resolve prompt template path relative to module location if not specified
    if prompt_path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        prompt_file = project_root / "prompts" / "semantic_matching.txt"
    else:
        prompt_file = Path(prompt_path)

    if not prompt_file.is_file():
        raise SemanticMatchingError(f"Prompt template file not found at: {prompt_file}")

    try:
        template_text = prompt_file.read_text(encoding="utf-8")
    except Exception as err:
        raise SemanticMatchingError(f"Failed to read prompt template file: {err}") from err

    candidate_json = candidate.model_dump_json(indent=2)
    job_json = job.model_dump_json(indent=2)

    prompt = (
        template_text.replace("{candidate_profile}", candidate_json).replace(
            "{job_profile}", job_json
        )
    )

    service = llm_service or LLMService()

    try:
        raw_output = service.generate_completion(prompt, format_json=True)
    except LLMServiceError:
        raise
    except Exception as err:
        raise SemanticMatchingError(f"Unexpected LLM generation error: {err}") from err

    if not raw_output or not raw_output.strip():
        raise SemanticMatchingError("Empty or whitespace LLM response output received")

    cleaned_json_str = _clean_json_response(raw_output)

    try:
        parsed_data = json.loads(cleaned_json_str)
    except json.JSONDecodeError as err:
        logger.error("LLM semantic JSON parsing failed: %s", err)
        raise SemanticMatchingError(f"Failed to parse LLM response as valid JSON: {err}") from err

    if not isinstance(parsed_data, dict):
        raise SemanticMatchingError(
            f"Expected JSON object dictionary from LLM, got {type(parsed_data).__name__}"
        )

    try:
        semantic_result = SemanticMatchResult.model_validate(parsed_data)
    except ValidationError as err:
        logger.error("SemanticMatchResult Pydantic validation failed: %s", err)
        raise SemanticMatchingError(
            f"LLM JSON output failed SemanticMatchResult schema validation: {err}"
        ) from err

    return semantic_result
