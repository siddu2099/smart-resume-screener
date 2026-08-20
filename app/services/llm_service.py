"""LLM service handling direct HTTP communication with local Ollama server."""

import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Custom exception raised when Ollama communication or generation fails."""

    pass


class LLMService:
    """Service wrapper for calling local Ollama HTTP API endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Initialize LLMService with environment defaults or explicit parameters.

        Args:
            base_url: Base URL for Ollama server (defaults to OLLAMA_BASE_URL env var or http://localhost:11434).
            model: Model name to invoke (defaults to OLLAMA_MODEL env var or qwen2.5:7b).
            timeout: Timeout in seconds for HTTP requests (defaults to OLLAMA_TIMEOUT env var or 60.0).
        """
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

        timeout_val = timeout
        if timeout_val is None:
            try:
                timeout_val = float(os.getenv("OLLAMA_TIMEOUT", "60"))
            except ValueError:
                timeout_val = 60.0
        self.timeout = timeout_val

    def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        format_json: bool = True,
    ) -> str:
        """Send generation request to Ollama /api/generate endpoint.

        Args:
            prompt: Formatted user prompt string.
            system_prompt: Optional system prompt instructions.
            format_json: Whether to request structured JSON output format.

        Returns:
            Raw generated string output from the LLM.

        Raises:
            LLMServiceError: If service is unavailable, request times out, or HTTP fails.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        start_time = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            logger.error("Ollama connection failed: base_url=%s", self.base_url)
            raise LLMServiceError(
                f"Ollama service is unavailable at {self.base_url}. Ensure Ollama is running."
            ) from err

        except httpx.TimeoutException as err:
            logger.error("Ollama request timed out after %.2f seconds", self.timeout)
            raise LLMServiceError(
                f"Ollama request timed out after {self.timeout} seconds."
            ) from err

        except httpx.HTTPStatusError as err:
            logger.error("Ollama HTTP status error: %d", err.response.status_code)
            raise LLMServiceError(
                f"Ollama HTTP error {err.response.status_code}: {err.response.text}"
            ) from err

        except httpx.RequestError as err:
            logger.error("Ollama HTTP request error: %s", err)
            raise LLMServiceError(f"Ollama request error: {err}") from err

        except Exception as err:
            logger.error("Unexpected error during Ollama generation: %s", err)
            raise LLMServiceError(f"Ollama generation failed: {err}") from err

        elapsed = time.time() - start_time
        logger.info(
            "Ollama generation completed: model=%s elapsed_seconds=%.2f",
            self.model,
            elapsed,
        )

        response_text = data.get("response")
        if not response_text or not isinstance(response_text, str) or not response_text.strip():
            raise LLMServiceError("Empty or invalid response output received from Ollama model")

        return response_text
