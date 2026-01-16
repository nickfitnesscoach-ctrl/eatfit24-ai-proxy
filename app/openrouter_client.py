# app/openrouter_client.py
import base64
import json
import logging
import asyncio
import re
from typing import Optional, List, Any, Tuple

import httpx
from json_repair import repair_json

from app.config import settings
from app.schemas import FoodItem, TotalNutrition

logger = logging.getLogger(__name__)

# Pattern to detect explicit weights in user comments (e.g., "150 г", "200 g")
GRAMS_PATTERN = re.compile(r"\b\d+\s*(г|гр|g)\b", re.IGNORECASE)

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 10.0
RETRY_BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 413, 422}

# OpenRouter request configuration
OPENROUTER_TIMEOUT = 20.0
OPENROUTER_MAX_TOKENS = 2000
OPENROUTER_IMAGE_DETAIL = "low"


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors."""


def safe_str(value: Any) -> str:
    """Safely convert any value to string for logging (never raises)."""
    try:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    except Exception:
        return repr(value)


def has_explicit_grams(user_comment: str | None) -> bool:
    if not user_comment:
        return False
    return bool(GRAMS_PATTERN.search(user_comment))


def build_food_recognition_prompt(
    user_comment: Optional[str] = None, locale: str = "ru"
) -> str:
    """
    IMPORTANT: This prompt is designed for OpenRouter native JSON mode (response_format=json_object).
    Therefore: NO chain-of-thought, NO extra text, ONLY JSON object output.
    """
    comment_text = (
        user_comment.strip() if user_comment and user_comment.strip() else None
    )
    has_weights = has_explicit_grams(comment_text)

    if locale == "ru":
        comment_section = f"""
=== КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ ===
{comment_text if comment_text else "Комментарий отсутствует"}
================================
"""
        weight_instruction = ""
        if has_weights:
            weight_instruction = "\n⚠️ ВАЖНО: ПОЛЬЗОВАТЕЛЬ УКАЗАЛ ТОЧНЫЕ ВЕСА ПРОДУКТОВ — НЕ МЕНЯЙ ИХ БЕЗ ЯВНОГО ПРОТИВОРЕЧИЯ С ФОТО."

        return f"""Ты — профессиональный диетолог-технолог. Твоя задача — оценить КБЖУ по фото максимально точно.
{comment_section}{weight_instruction}

ПРАВИЛА:
1) Распознавай ВСЮ ЕДУ И НАПИТКИ на фото. Игнорируй фоновые объекты (стол, техника, руки, мебель).
2) Если комментарий пустой или содержит только название блюда — верни ОДНО блюдо целиком.
3) Если в комментарии перечислены ингредиенты — верни каждый ингредиент отдельной строкой в items.
4) Если в комментарии указаны веса (например: "курица 150 г, рис 200 г"):
   - Считай эти веса основным источником правды
   - Не меняй grams, кроме явного противоречия с фото
   - Если сомневаешься — оставь веса и опиши сомнения в model_notes
5) ВАЖНО: Даже если на фото только один предмет без контекста (фрукт, овощ, продукт) — распознай его и оцени
6) НЕ УГАДЫВАЙ: Если не можешь определить что это за еда — верни items=[] и укажи причину в model_notes

ОТВЕТ: ВЕРНИ ТОЛЬКО ВАЛИДНЫЙ JSON ОБЪЕКТ (без текста/markdown).

ФОРМАТ:
{{
  "items": [
    {{
      "name": "название продукта (ТОЛЬКО РУССКИЙ язык)",
      "grams": число,
      "kcal": число,
      "protein": число,
      "fat": число,
      "carbohydrates": число
    }}
  ],
  "total": {{
    "kcal": число,
    "protein": число,
    "fat": число,
    "carbohydrates": число
  }},
  "model_notes": "краткие комментарии (ТОЛЬКО РУССКИЙ язык)"
}}

ЯЗЫКОВОЕ ПРАВИЛО: name и model_notes ТОЛЬКО НА РУССКОМ языке.
"""
    else:
        comment_section = f"""
=== USER COMMENT ===
{comment_text if comment_text else "No comment provided"}
====================
"""
        weight_instruction = ""
        if has_weights:
            weight_instruction = "\n⚠️ IMPORTANT: USER PROVIDED EXACT WEIGHTS — DO NOT CHANGE THEM WITHOUT EXPLICIT CONTRADICTION WITH THE PHOTO."
        return f"""You are a nutrition expert. Estimate nutrition from a photo.
{comment_section}{weight_instruction}

RULES:
- Recognize all food and drinks; ignore background objects.
- If comment is empty or only dish name: return ONE dish item.
- If comment lists ingredients: return each ingredient as a separate item.
- If comment includes grams: treat them as primary truth; do not change unless photo contradicts.
- IMPORTANT: Even if photo shows only a single item without context (fruit, vegetable, product) — recognize it and estimate
- DO NOT GUESS: If you cannot determine what food this is — return items=[] and explain in model_notes

OUTPUT: ONLY a valid JSON object (no markdown, no extra text).

FORMAT:
{{
  "items": [
    {{
      "name": "product/dish name",
      "grams": number,
      "kcal": number,
      "protein": number,
      "fat": number,
      "carbohydrates": number
    }}
  ],
  "total": {{
    "kcal": number,
    "protein": number,
    "fat": number,
    "carbohydrates": number
  }},
  "model_notes": "brief notes"
}}
"""


def normalize_item_fields(item: dict) -> dict:
    """Normalize alternative field names to SSOT."""
    if not isinstance(item, dict):
        raise OpenRouterError(f"AI item must be an object, got: {type(item).__name__}")

    normalized = dict(item)

    # carbs -> carbohydrates
    if "carbs" in normalized and "carbohydrates" not in normalized:
        normalized["carbohydrates"] = normalized.pop("carbs")

    # calories -> kcal
    if "calories" in normalized and "kcal" not in normalized:
        normalized["kcal"] = normalized.pop("calories")

    # amount_grams -> grams
    if "amount_grams" in normalized and "grams" not in normalized:
        normalized["grams"] = normalized.pop("amount_grams")

    return normalized


def _ensure_dict(obj: Any, context: str) -> dict:
    """Ensure obj is a dict; try json.loads if it's a JSON string; otherwise raise."""
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    logger.error(
        "%s: expected dict, got %s: %s", context, type(obj).__name__, safe_str(obj)
    )
    raise OpenRouterError(f"{context}: expected JSON object")


def parse_ai_response(response_text: str) -> Tuple[List[FoodItem], Optional[str]]:
    """
    Parse AI model response (expected JSON object).
    Uses json_repair for robustness, but MUST enforce dict/list types.
    """
    try:
        data = repair_json(response_text, return_objects=True)
        data = _ensure_dict(data, "AI response root")

        items_raw = data.get("items", []) or []
        if not isinstance(items_raw, list):
            logger.error("AI response items is not a list: %s", safe_str(items_raw))
            raise OpenRouterError("AI response items must be a list")

        items: List[FoodItem] = []
        for item_data in items_raw:
            if not isinstance(item_data, dict):
                logger.error("AI item is not object: %s", safe_str(item_data))
                raise OpenRouterError("AI item must be an object")

            normalized = normalize_item_fields(item_data)

            # Required fields
            try:
                items.append(
                    FoodItem(
                        name=str(normalized["name"]),
                        grams=float(normalized["grams"]),
                        kcal=float(normalized["kcal"]),
                        protein=float(normalized["protein"]),
                        fat=float(normalized["fat"]),
                        carbohydrates=float(normalized["carbohydrates"]),
                    )
                )
            except KeyError as e:
                logger.error(
                    "Missing field in AI item: %s item=%s", str(e), safe_str(normalized)
                )
                raise OpenRouterError(f"Missing required field: {e}")
            except (TypeError, ValueError) as e:
                logger.error(
                    "Invalid field types in AI item: %s item=%s",
                    safe_str(e),
                    safe_str(normalized),
                )
                raise OpenRouterError(f"Invalid field types: {e}")

        model_notes = data.get("model_notes")
        if model_notes is not None and not isinstance(model_notes, str):
            model_notes = safe_str(model_notes)

        return items, model_notes

    except OpenRouterError:
        raise
    except Exception as e:
        logger.error(
            "Failed to parse AI response: %s raw=%s",
            safe_str(e),
            safe_str(response_text)[:800],
        )
        raise OpenRouterError(f"Failed to parse AI response: {e}")


async def _make_openrouter_request(
    client: httpx.AsyncClient, url: str, headers: dict, payload: dict
) -> httpx.Response:
    last_exception: Exception | None = None

    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < RETRY_MAX_ATTEMPTS:
                    delay = min(
                        RETRY_INITIAL_DELAY
                        * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                        RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "OpenRouter returned %s, retrying in %.1fs (attempt %s/%s)",
                        response.status_code,
                        delay,
                        attempt,
                        RETRY_MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "OpenRouter returned %s after %s attempts",
                    response.status_code,
                    RETRY_MAX_ATTEMPTS,
                )
                return response

            return response

        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < RETRY_MAX_ATTEMPTS:
                delay = min(
                    RETRY_INITIAL_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                    RETRY_MAX_DELAY,
                )
                logger.warning(
                    "OpenRouter timeout, retrying in %.1fs (attempt %s/%s)",
                    delay,
                    attempt,
                    RETRY_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            logger.error("OpenRouter timeout after %s attempts", RETRY_MAX_ATTEMPTS)
            raise

        except httpx.RequestError as e:
            last_exception = e
            if attempt < RETRY_MAX_ATTEMPTS:
                delay = min(
                    RETRY_INITIAL_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                    RETRY_MAX_DELAY,
                )
                logger.warning(
                    "OpenRouter request error (%s), retrying in %.1fs (attempt %s/%s)",
                    type(e).__name__,
                    delay,
                    attempt,
                    RETRY_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            logger.error(
                "OpenRouter request error after %s attempts: %s",
                RETRY_MAX_ATTEMPTS,
                safe_str(e),
            )
            raise

    if last_exception:
        raise last_exception
    raise OpenRouterError("Unexpected retry loop exit")


async def recognize_food_with_bytes(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru",
) -> Tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    b64_image = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64_image}"

    try:
        prompt = build_food_recognition_prompt(user_comment, locale)

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://eatfit24.com",
            "X-Title": "EatFit24",
        }

        payload = {
            "model": settings.openrouter_model,
            "max_tokens": OPENROUTER_MAX_TOKENS,
            "response_format": {"type": "json_object"},  # Native JSON mode
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                                "detail": OPENROUTER_IMAGE_DETAIL,
                            },
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
            response = await _make_openrouter_request(
                client,
                f"{settings.openrouter_base_url}/chat/completions",
                headers,
                payload,
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(
                    "OpenRouter API error: status=%s body=%s",
                    response.status_code,
                    safe_str(error_detail),
                )
                raise OpenRouterError(
                    f"OpenRouter API returned {response.status_code}: {error_detail}"
                )

            # Robust JSON decoding
            try:
                result = response.json()
            except Exception as e:
                logger.error(
                    "OpenRouter response is not JSON. err=%s body=%s",
                    safe_str(e),
                    safe_str(response.text),
                )
                raise OpenRouterError("OpenRouter returned invalid JSON")

            if not isinstance(result, dict):
                logger.error(
                    "OpenRouter returned non-object JSON. type=%s value=%s",
                    type(result).__name__,
                    safe_str(result),
                )
                raise OpenRouterError(
                    "OpenRouter returned non-object JSON (expected dict)"
                )

            usage = result.get("usage")
            if isinstance(usage, dict):
                logger.info(
                    "OpenRouter token usage: prompt=%s completion=%s total=%s",
                    usage.get("prompt_tokens", "N/A"),
                    usage.get("completion_tokens", "N/A"),
                    usage.get("total_tokens", "N/A"),
                )

            try:
                ai_response_text = result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(
                    "Unexpected OpenRouter response structure: %s body=%s",
                    safe_str(e),
                    safe_str(result)[:2000],
                )
                raise OpenRouterError("Unexpected response structure from OpenRouter")

            # Safe debug log
            logger.info("AI response (first 800 chars): %s", ai_response_text[:800])

            items, model_notes = parse_ai_response(ai_response_text)

            total = TotalNutrition(
                kcal=sum(item.kcal for item in items),
                protein=sum(item.protein for item in items),
                fat=sum(item.fat for item in items),
                carbohydrates=sum(item.carbohydrates for item in items),
            )

            return items, total, model_notes

    except httpx.TimeoutException:
        logger.error("OpenRouter API request timed out")
        raise OpenRouterError("Request to OpenRouter API timed out")
    except httpx.RequestError as e:
        logger.error("OpenRouter API request failed: %s", safe_str(e))
        raise OpenRouterError(f"Failed to connect to OpenRouter API: {e}")
    except OpenRouterError:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in recognize_food_with_bytes: %s",
            safe_str(e),
            exc_info=True,
        )
        raise OpenRouterError(f"Unexpected error: {e}")
