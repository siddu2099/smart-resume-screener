"""LLM-driven semantic candidate-job matching evaluation service."""

import json
import re
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError

from app.schemas.job import JobProfile
from app.schemas.matching import SemanticMatchResult
from app.schemas.resume import CandidateProfile
from app.services.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)



def sanitize_semantic_explanation(
    text: str,
    required_skills: list[str],
    missing_skills: list[str],
    has_education: bool,
) -> str:
    """Sanitize LLM semantic text output against deterministic facts.

    Ensures:
    - Required skills are never described as preferred.
    - False claims of no education requirement are stripped when an education requirement exists.
    """
    if not text or not isinstance(text, str):
        return text

    result = text

    # Correct any misclassification of required skills as preferred
    for s in required_skills:
        if not s or not s.strip():
            continue
        s_clean = s.strip()
        # Case 1: "Skill, which is a preferred skill" -> "Skill, which is a required skill"
        pattern1 = re.compile(r'(\b' + re.escape(s_clean) + r'\b[^.!\n]*?)\bpreferred(\s+skill|\s+qualification|\s+requirement)?\b', re.IGNORECASE)
        result = pattern1.sub(r'\1required\2', result)

        # Case 2: "preferred skill Skill" -> "required skill Skill"
        pattern2 = re.compile(r'\bpreferred(\s+skill|\s+qualification|\s+requirement)?\b([^.!\n]*?\b' + re.escape(s_clean) + r'\b)', re.IGNORECASE)
        result = pattern2.sub(r'required\1\2', result)

    # Remove 'no education requirement' claims if job has an explicit education requirement
    if has_education:
        result = re.sub(r'[^.!\n]*\bno\s+(?:explicit\s+)?education\s+requirement[^\n.!]*[.!]?', '', result, flags=re.IGNORECASE)
        result = re.sub(r'\s+', ' ', result).strip()

    return result.strip()


def sanitize_semantic_result(
    semantic_result: SemanticMatchResult,
    job: JobProfile,
    missing_required_skills: Optional[list[str]] = None,
) -> SemanticMatchResult:
    """Sanitize a SemanticMatchResult against deterministic JobProfile facts."""
    if semantic_result is None:
        return sanitize_semantic_result(semantic_result, job)

    req_skills = job.required_skills or []
    missing_skills = missing_required_skills or []
    has_edu = bool(job.education and job.education.strip())

    missing_norm = {s.lower() for s in missing_skills}

    # Sanitize strengths list
    clean_strengths = []
    for st in semantic_result.strengths or []:
        if not st or not st.strip():
            continue
        text = st.strip()
        text_lower = text.lower()

        # Reject claims of no education requirement if job has education requirement
        if has_edu and ('no explicit education' in text_lower or 'no education requirement' in text_lower):
            continue

        # Reject strengths claiming candidate possesses a missing required skill
        is_contradictory = False
        for ms in missing_norm:
            if ms in text_lower:
                if any(kw in text_lower for kw in ['has ', 'proficient', 'knows', 'experience with', 'matched', 'satisfies', 'possesses', 'skilled in']):
                    is_contradictory = True
                    break
        if is_contradictory:
            continue

        # Sanitize any required skill described as preferred
        text = sanitize_semantic_explanation(text, req_skills, missing_skills, has_edu)
        if text and text not in clean_strengths:
            clean_strengths.append(text)

    # Sanitize gaps list
    clean_gaps = []
    for gp in semantic_result.gaps or []:
        if not gp or not gp.strip():
            continue
        text = gp.strip()
        text_lower = text.lower()

        # Reject claims of no education requirement in gaps if job has education requirement
        if has_edu and ('no explicit education' in text_lower or 'no education requirement' in text_lower):
            continue

        text = sanitize_semantic_explanation(text, req_skills, missing_skills, has_edu)
        if text and text not in clean_gaps:
            clean_gaps.append(text)

    # Sanitize justification text
    clean_justification = sanitize_semantic_explanation(
        semantic_result.justification or '',
        req_skills,
        missing_skills,
        has_edu,
    )

    return SemanticMatchResult(
        semantic_score=semantic_result.semantic_score,
        strengths=clean_strengths,
        gaps=clean_gaps,
        justification=clean_justification,
    )


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
