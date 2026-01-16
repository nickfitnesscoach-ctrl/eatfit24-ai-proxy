# app/food_gate.py
"""
Food Detection Gate (Anti-Hallucination)

Lightweight LLM check to determine if an image contains food
before running expensive recognition.
"""

import base64
import logging

import httpx
from json_repair import repair_json

from app.config import settings
from app.openrouter_client import OpenRouterError
from app.schemas import GateResult

logger = logging.getLogger(__name__)

# Gate-specific configuration (lighter than main recognition)
GATE_MAX_TOKENS = 200
GATE_TIMEOUT = 15.0


def build_gate_prompt(locale: str = "ru") -> str:
    """
    Build a strict food detection prompt.
    Returns ONLY JSON, no explanation.
    """
    if locale == "ru":
        return """Проанализируй изображение. Это фотография еды?

ПРАВИЛА:
- Еда должна быть ВИДИМОЙ и ГЛАВНОЙ в кадре
- Скриншоты, мемы, интерфейсы, животные, лица, документы → is_food=false
- Если сомневаешься — is_food=false (НЕ УГАДЫВАЙ)

ОТВЕТ: Только валидный JSON:
{"is_food": boolean, "confidence": float от 0 до 1, "reason": "короткая причина"}"""
    else:
        return """Analyze the image. Is this a photo of food?

RULES:
- Food must be VISIBLE and DOMINANT in the frame
- Screenshots, memes, interfaces, animals, faces, documents → is_food=false
- If unsure → is_food=false (DO NOT GUESS)

OUTPUT: Only valid JSON:
{"is_food": boolean, "confidence": float 0-1, "reason": "short reason"}"""


def parse_gate_response(response_text: str) -> GateResult:
    """
    Parse gate LLM response with hardening.
    If parsing fails, returns conservative result (not food).
    """
    try:
        # Try json_repair for robustness
        data = repair_json(response_text, return_objects=True)

        if not isinstance(data, dict):
            logger.warning("Gate response is not a dict: %s", type(data).__name__)
            return GateResult(is_food=False, confidence=0.0, reason="gate_parse_error")

        is_food = bool(data.get("is_food", False))
        confidence = float(data.get("confidence", 0.0))
        reason = str(data.get("reason", "unknown"))

        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        return GateResult(is_food=is_food, confidence=confidence, reason=reason)

    except Exception as e:
        logger.warning("Gate parse error: %s, raw: %s", str(e), response_text[:200])
        return GateResult(is_food=False, confidence=0.0, reason="gate_parse_error")


async def check_food_gate(
    image_bytes: bytes,
    content_type: str,
    locale: str = "ru",
) -> GateResult:
    """
    Run lightweight food detection gate.

    Returns GateResult with is_food, confidence, reason.
    On any error (network, parse, etc.), returns conservative result.
    """
    b64_image = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64_image}"

    prompt = build_gate_prompt(locale)

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://eatfit24.com",
        "X-Title": "EatFit24-Gate",
    }

    payload = {
        "model": settings.openrouter_model,
        "max_tokens": GATE_MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                            "detail": "low",  # Faster, cheaper
                        },
                    },
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=GATE_TIMEOUT) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code == 429:
                logger.warning("Gate: rate limited")
                raise OpenRouterError("Gate rate limited (429)")

            if response.status_code != 200:
                logger.error(
                    "Gate API error: %s %s", response.status_code, response.text[:200]
                )
                raise OpenRouterError(
                    f"Gate API error: {response.status_code} {response.text[:200]}"
                )

            result = response.json()
            if not isinstance(result, dict):
                logger.error("Gate: non-dict response")
                return GateResult(
                    is_food=False, confidence=0.0, reason="gate_parse_error"
                )

            try:
                ai_text = result["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error("Gate: unexpected structure: %s", str(e))
                return GateResult(
                    is_food=False, confidence=0.0, reason="gate_parse_error"
                )

            return parse_gate_response(ai_text)

    except httpx.TimeoutException:
        logger.warning("Gate: timeout")
        raise OpenRouterError("Gate timeout")
    except httpx.RequestError as e:
        logger.warning("Gate: request error: %s", str(e))
        raise OpenRouterError(f"Gate network error: {str(e)}")
    except OpenRouterError:
        raise
    except Exception as e:
        logger.error("Gate: unexpected error: %s", str(e), exc_info=True)
        # For completely unexpected runtime errors, safe fail-closed might still be appropriate,
        # OR raise to let main handle as 500. Let's raise to avoid silent swallowed errors.
        raise OpenRouterError(f"Gate internal error: {str(e)}")
