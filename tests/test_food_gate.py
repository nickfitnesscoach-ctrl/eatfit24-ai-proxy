# tests/test_food_gate.py
"""
Unit tests for food gate (mocked LLM responses).
No real API calls - fast and reproducible.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from app.food_gate import parse_gate_response, check_food_gate
from app.schemas import GateResult
from app.openrouter_client import OpenRouterError


class TestParseGateResponse:
    """Test gate response parsing with various inputs."""

    def test_valid_food_response(self):
        """Valid JSON with food detected."""
        response = json.dumps(
            {"is_food": True, "confidence": 0.85, "reason": "food visible on plate"}
        )
        result = parse_gate_response(response)

        assert result.is_food is True
        assert result.confidence == 0.85
        assert result.reason == "food visible on plate"

    def test_valid_not_food_response(self):
        """Valid JSON with no food detected."""
        response = json.dumps(
            {"is_food": False, "confidence": 0.12, "reason": "screenshot of app"}
        )
        result = parse_gate_response(response)

        assert result.is_food is False
        assert result.confidence == 0.12
        assert result.reason == "screenshot of app"

    def test_garbage_response(self):
        """Non-JSON garbage should return conservative result."""
        result = parse_gate_response("this is not json at all!!!")

        assert result.is_food is False
        assert result.confidence == 0.0
        assert result.reason == "gate_parse_error"

    def test_empty_response(self):
        """Empty string should return conservative result."""
        result = parse_gate_response("")

        assert result.is_food is False
        assert result.confidence == 0.0
        assert result.reason == "gate_parse_error"

    def test_partial_json(self):
        """Partial/broken JSON should return conservative result."""
        result = parse_gate_response('{"is_food": true, "confide')

        # json_repair might fix some partial JSON, but if not - conservative
        assert isinstance(result, GateResult)
        # Result could vary based on json_repair behavior
        if not result.is_food:
            assert result.reason in ["gate_parse_error", "unknown"]

    def test_confidence_clamped_high(self):
        """Confidence > 1 should be clamped to 1."""
        response = json.dumps(
            {
                "is_food": True,
                "confidence": 1.5,  # Invalid, should clamp
                "reason": "test",
            }
        )
        result = parse_gate_response(response)

        assert result.confidence == 1.0

    def test_confidence_clamped_low(self):
        """Confidence < 0 should be clamped to 0."""
        response = json.dumps(
            {
                "is_food": True,
                "confidence": -0.5,  # Invalid, should clamp
                "reason": "test",
            }
        )
        result = parse_gate_response(response)

        assert result.confidence == 0.0

    def test_missing_fields_defaults(self):
        """Missing fields should use safe defaults."""
        response = json.dumps({})
        result = parse_gate_response(response)

        assert result.is_food is False  # Default to false (conservative)
        assert result.confidence == 0.0
        assert result.reason == "unknown"

    def test_markdown_wrapped_json(self):
        """JSON wrapped in markdown should still parse (json_repair helps)."""
        response = """```json
{
    "is_food": true,
    "confidence": 0.9,
    "reason": "salad visible"
}
```"""
        result = parse_gate_response(response)

        # json_repair should handle this
        assert result.is_food is True
        assert result.confidence == 0.9


class TestCheckFoodGate:
    """Test the full gate check flow with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_food_detection(self):
        """Gate correctly identifies food image."""
        response_json = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_food": True,
                                "confidence": 0.88,
                                "reason": "pizza visible",
                            }
                        )
                    }
                }
            ]
        }

        # Create a proper mock response object (json() is sync in httpx)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_json
        mock_response.text = json.dumps(response_json)

        with patch("app.food_gate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            result = await check_food_gate(
                image_bytes=b"fake_image_data", content_type="image/jpeg", locale="ru"
            )

            assert result.is_food is True
            assert result.confidence == 0.88
            assert result.reason == "pizza visible"

    @pytest.mark.asyncio
    async def test_not_food_detection(self):
        """Gate correctly rejects non-food image."""
        response_json = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_food": False,
                                "confidence": 0.05,
                                "reason": "cat photo",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_json
        mock_response.text = json.dumps(response_json)

        with patch("app.food_gate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            result = await check_food_gate(
                image_bytes=b"fake_image_data",
                content_type="image/jpeg",
            )

            assert result.is_food is False
            assert result.confidence == 0.05

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Rate limit raises OpenRouterError."""
        with patch("app.food_gate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value.status_code = 429
            mock_instance.post.return_value.text = "Rate limited"

            with pytest.raises(OpenRouterError, match="Gate rate limited"):
                await check_food_gate(
                    image_bytes=b"fake_image_data",
                    content_type="image/jpeg",
                )

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """API error raises OpenRouterError."""
        with patch("app.food_gate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value.status_code = 500
            mock_instance.post.return_value.text = "Internal Server Error"

            with pytest.raises(OpenRouterError, match="500"):
                await check_food_gate(
                    image_bytes=b"fake_image_data",
                    content_type="image/jpeg",
                )

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Timeout raises OpenRouterError."""
        import httpx

        with patch("app.food_gate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(OpenRouterError, match="timeout"):
                await check_food_gate(
                    image_bytes=b"fake_image_data",
                    content_type="image/jpeg",
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
