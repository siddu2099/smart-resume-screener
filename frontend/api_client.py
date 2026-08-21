"""Typed REST API client for communicating with FastAPI backend.

Strict isolation: This client depends ONLY on `httpx` and standard library modules.
Zero imports from SQLAlchemy, database models, or LLM services.
"""

import os
from typing import Any, Optional

import httpx

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0


class APIClientError(Exception):
    """Base exception for all API client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or message


class APIConnectionError(APIClientError):
    """Raised when connecting to the API backend fails."""

    pass


class APITimeoutError(APIClientError):
    """Raised when an API request times out."""

    pass


class APIHTTPError(APIClientError):
    """Raised when the API returns an HTTP error status (4xx / 5xx)."""

    pass


class ScreenerAPIClient:
    """HTTP client wrapper for Smart Resume Screener REST API endpoints."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        """Initialize API client.

        Args:
            base_url: Base URL for FastAPI server. Defaults to API_BASE_URL env var or http://127.0.0.1:8000.
            timeout: HTTP request timeout in seconds.
        """
        env_url = os.getenv("API_BASE_URL")
        self.base_url = (base_url or env_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create reusable httpx Client instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client connection pool."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with centralized error handling."""
        client = self._get_client()
        try:
            response = client.request(method=method, url=endpoint, json=json, files=files)
        except httpx.TimeoutException as err:
            raise APITimeoutError(
                f"API request to {endpoint} timed out after {self.timeout}s",
                detail=str(err),
            ) from err
        except httpx.RequestError as err:
            raise APIConnectionError(
                f"Failed to connect to API backend at {self.base_url}: {err}",
                detail=str(err),
            ) from err

        if not response.is_success:
            detail_msg = f"HTTP {response.status_code} Error"
            try:
                err_data = response.json()
                if isinstance(err_data, dict) and "detail" in err_data:
                    detail_msg = str(err_data["detail"])
            except Exception:
                detail_msg = response.text or detail_msg

            raise APIHTTPError(
                message=f"API Error ({response.status_code}): {detail_msg}",
                status_code=response.status_code,
                detail=detail_msg,
            )

        try:
            return response.json()
        except Exception as err:
            raise APIClientError(
                f"Failed to parse JSON response from {endpoint}: {err}",
                status_code=response.status_code,
            ) from err

    def health_check(self) -> dict[str, Any]:
        """Check API backend health endpoint (GET /health)."""
        return self._request("GET", "/health")

    def upload_resume(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """Upload resume PDF and ingest candidate profile (POST /resumes)."""
        files = {"file": (filename, file_bytes, "application/pdf")}
        return self._request("POST", "/resumes", files=files)

    def create_job(self, description: str) -> dict[str, Any]:
        """Ingest job description text and create job posting (POST /jobs)."""
        return self._request("POST", "/jobs", json={"description": description})

    def create_match(self, candidate_id: int, job_id: int) -> dict[str, Any]:
        """Evaluate candidate against job and persist match result (POST /matches)."""
        return self._request("POST", "/matches", json={"candidate_id": candidate_id, "job_id": job_id})

    def get_match(self, match_id: int) -> dict[str, Any]:
        """Retrieve match evaluation result by ID (GET /matches/{match_id})."""
        return self._request("GET", f"/matches/{match_id}")

    def get_shortlist(self, job_id: int) -> dict[str, Any]:
        """Retrieve ranked candidate shortlist for job posting (GET /jobs/{job_id}/shortlist)."""
        return self._request("GET", f"/jobs/{job_id}/shortlist")
