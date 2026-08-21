"""Unit tests for frontend API client module and error handling."""

import os
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest

from frontend.api_client import (
    APIClientError,
    APIConnectionError,
    APIHTTPError,
    APITimeoutError,
    ScreenerAPIClient,
)


@pytest.fixture
def mock_httpx_client():
    """Fixture providing a mocked httpx.Client instance."""
    with patch("httpx.Client") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


# --- 1. Successful API Calls ---

def test_upload_resume_success(mock_httpx_client):
    """Test successful resume upload request."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"candidate_id": 1, "name": "Alice"}
    mock_httpx_client.request.return_value = mock_resp

    with ScreenerAPIClient(base_url="http://localhost:8000") as client:
        res = client.upload_resume(b"%PDF-1.4...", "alice.pdf")
        assert res["candidate_id"] == 1
        assert res["name"] == "Alice"

    mock_httpx_client.request.assert_called_once()
    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "/resumes"


def test_create_job_success(mock_httpx_client):
    """Test successful job creation request."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"job_id": 10, "title": "Dev"}
    mock_httpx_client.request.return_value = mock_resp

    with ScreenerAPIClient() as client:
        res = client.create_job("Python Job Description")
        assert res["job_id"] == 10

    mock_httpx_client.request.assert_called_once()
    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "/jobs"
    assert kwargs["json"] == {"description": "Python Job Description"}


def test_create_match_success(mock_httpx_client):
    """Test successful candidate-job match evaluation request."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"candidate_id": 1, "job_id": 10, "status": "Strong Match"}
    mock_httpx_client.request.return_value = mock_resp

    with ScreenerAPIClient() as client:
        res = client.create_match(candidate_id=1, job_id=10)
        assert res["status"] == "Strong Match"

    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["url"] == "/matches"
    assert kwargs["json"] == {"candidate_id": 1, "job_id": 10}


def test_get_match_success(mock_httpx_client):
    """Test successful match retrieval by ID."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"candidate_id": 1, "job_id": 10, "status": "Strong Match"}
    mock_httpx_client.request.return_value = mock_resp

    with ScreenerAPIClient() as client:
        res = client.get_match(match_id=5)
        assert res["candidate_id"] == 1

    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "/matches/5"


def test_get_shortlist_success(mock_httpx_client):
    """Test successful job shortlist retrieval."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"job_id": 10, "candidates": [{"candidate_id": 1}]}
    mock_httpx_client.request.return_value = mock_resp

    with ScreenerAPIClient() as client:
        res = client.get_shortlist(job_id=10)
        assert res["job_id"] == 10
        assert len(res["candidates"]) == 1

    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "/jobs/10/shortlist"


# --- 2. HTTP Error Handling Tests ---

def test_api_http_400_error(mock_httpx_client):
    """Test HTTP 400 Bad Request error handling."""
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"detail": "Invalid PDF signature"}
    mock_httpx_client.request.return_value = mock_resp

    client = ScreenerAPIClient()
    with pytest.raises(APIHTTPError) as exc_info:
        client.upload_resume(b"bad bytes", "file.txt")

    assert exc_info.value.status_code == 400
    assert "Invalid PDF signature" in exc_info.value.detail


def test_api_http_404_error(mock_httpx_client):
    """Test HTTP 404 Not Found error handling."""
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "Job with ID 99 not found"}
    mock_httpx_client.request.return_value = mock_resp

    client = ScreenerAPIClient()
    with pytest.raises(APIHTTPError) as exc_info:
        client.get_shortlist(99)

    assert exc_info.value.status_code == 404
    assert "Job with ID 99 not found" in exc_info.value.detail


def test_api_http_422_error(mock_httpx_client):
    """Test HTTP 422 Unprocessable Entity error handling."""
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 422
    mock_resp.json.return_value = {"detail": "Unprocessable resume text"}
    mock_httpx_client.request.return_value = mock_resp

    client = ScreenerAPIClient()
    with pytest.raises(APIHTTPError) as exc_info:
        client.upload_resume(b"%PDF...", "resume.pdf")

    assert exc_info.value.status_code == 422


def test_api_http_503_error(mock_httpx_client):
    """Test HTTP 503 Service Unavailable error handling."""
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 503
    mock_resp.json.return_value = {"detail": "Ollama service unavailable"}
    mock_httpx_client.request.return_value = mock_resp

    client = ScreenerAPIClient()
    with pytest.raises(APIHTTPError) as exc_info:
        client.create_match(1, 10)

    assert exc_info.value.status_code == 503
    assert "Ollama service unavailable" in exc_info.value.detail


# --- 3. Network & Connection Error Tests ---

def test_api_connection_failure(mock_httpx_client):
    """Test connection failure handling when backend is unreachable."""
    mock_httpx_client.request.side_effect = httpx.ConnectError("Connection refused")

    client = ScreenerAPIClient()
    with pytest.raises(APIConnectionError) as exc_info:
        client.health_check()

    assert "Failed to connect" in exc_info.value.message


def test_api_timeout_error(mock_httpx_client):
    """Test request timeout handling."""
    mock_httpx_client.request.side_effect = httpx.TimeoutException("Read timeout")

    client = ScreenerAPIClient()
    with pytest.raises(APITimeoutError) as exc_info:
        client.create_match(1, 1)

    assert "timed out" in exc_info.value.message


# --- 4. Environment Variable Configuration ---

def test_api_base_url_env_configuration(monkeypatch):
    """Test API_BASE_URL environment variable override."""
    monkeypatch.setenv("API_BASE_URL", "http://screener.internal:9000/")
    client = ScreenerAPIClient()
    assert client.base_url == "http://screener.internal:9000"


# --- 5. Static Architectural Isolation Assertion ---

def test_frontend_zero_backend_imports():
    """Statically verify frontend modules do not import database, ORM models, or LLM services."""
    import ast
    from pathlib import Path

    frontend_dir = Path(__file__).parent.parent / "frontend"
    for py_file in frontend_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("app"), f"Forbidden import '{alias.name}' in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("app"), f"Forbidden import from '{node.module}' in {py_file.name}"


def test_api_timeout_env_configuration(monkeypatch):
    """Test API_TIMEOUT environment variable configuration."""
    monkeypatch.setenv("API_TIMEOUT", "150.0")
    client = ScreenerAPIClient()
    assert client.timeout == 150.0

def test_api_timeout_custom_and_default():
    """Test explicit timeout parameter and default 120.0s timeout."""
    client_default = ScreenerAPIClient()
    assert client_default.timeout == 120.0

    client_custom = ScreenerAPIClient(timeout=45.0)
    assert client_custom.timeout == 45.0
