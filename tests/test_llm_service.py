"""Unit tests for LLMService HTTP client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.llm_service import LLMService, LLMServiceError


def test_llm_service_init_defaults():
    """Test LLMService default initialization from environment."""
    service = LLMService()
    assert service.base_url == "http://localhost:11434"
    assert service.model == "qwen2.5:7b"
    assert service.timeout == 60.0


def test_llm_service_custom_config():
    """Test LLMService custom configuration parameters."""
    service = LLMService(
        base_url="http://custom-ollama:11434/",
        model="custom-model:latest",
        timeout=30.0,
    )
    assert service.base_url == "http://custom-ollama:11434"
    assert service.model == "custom-model:latest"
    assert service.timeout == 30.0


@patch("httpx.Client.post")
def test_llm_service_successful_generation(mock_post):
    """Test successful generation response from Ollama API."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": '{"name": "Test Candidate"}'}
    mock_post.return_value = mock_response

    service = LLMService()
    result = service.generate_completion("Test prompt", format_json=True)

    assert result == '{"name": "Test Candidate"}'
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "qwen2.5:7b"
    assert kwargs["json"]["format"] == "json"


@patch("httpx.Client.post")
def test_llm_service_connection_error(mock_post):
    """Test that httpx.ConnectError raises LLMServiceError."""
    mock_post.side_effect = httpx.ConnectError("Connection refused")

    service = LLMService()
    with pytest.raises(LLMServiceError, match="unavailable"):
        service.generate_completion("Prompt")


@patch("httpx.Client.post")
def test_llm_service_timeout_error(mock_post):
    """Test that httpx.TimeoutException raises LLMServiceError."""
    mock_post.side_effect = httpx.TimeoutException("Request timed out")

    service = LLMService()
    with pytest.raises(LLMServiceError, match="timed out"):
        service.generate_completion("Prompt")


@patch("httpx.Client.post")
def test_llm_service_http_status_error(mock_post):
    """Test that httpx.HTTPStatusError raises LLMServiceError."""
    mock_res = MagicMock()
    mock_res.status_code = 500
    mock_res.text = "Internal Server Error"
    mock_post.side_effect = httpx.HTTPStatusError("500 Error", request=MagicMock(), response=mock_res)

    service = LLMService()
    with pytest.raises(LLMServiceError, match="HTTP error 500"):
        service.generate_completion("Prompt")


@patch("httpx.Client.post")
def test_llm_service_empty_response(mock_post):
    """Test that empty response body raises LLMServiceError."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "   "}
    mock_post.return_value = mock_response

    service = LLMService()
    with pytest.raises(LLMServiceError, match="Empty or invalid response output"):
        service.generate_completion("Prompt")
