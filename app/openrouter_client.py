import base64
import logging
import asyncio
import re
from typing import Optional, List
import httpx
from json_repair import repair_json
from app.config import settings
from app.schemas import FoodItem, TotalNutrition

logger = logging.getLogger(__name__)

# Pattern to detect explicit weights in user comments (e.g., "150 г", "200 g")
GRAMS_PATTERN = re.compile(r"\b\d+\s*(г|гр|g)\b", re.IGNORECASE)

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 10.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 413, 422}

# JSON validation retry configuration
# DISABLED: json_repair + native JSON mode handle all edge cases automatically
# No need for retry loop - if it fails, retry won't help
JSON_RETRY_ENABLED = False  # No JSON retries (was causing 2-minute waits)

# OpenRouter request configuration
OPENROUTER_TIMEOUT = 20.0  # seconds (P0: faster failure detection, was 30.0)
OPENROUTER_MAX_TOKENS = 2000  # Sufficient for complete JSON response (prevents truncation)
OPENROUTER_IMAGE_DETAIL = "low"  # P1.4 - cost optimization


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""

    pass


def has_explicit_grams(user_comment: str | None) -> bool:
    """
    Check if user comment contains explicit weight measurements

    Args:
        user_comment: User's comment about the food

    Returns:
        True if comment contains weight measurements like "150 г", "200 g"
    """
    if not user_comment:
        return False
    return bool(GRAMS_PATTERN.search(user_comment))


def build_food_recognition_prompt(
    user_comment: Optional[str] = None, locale: str = "ru"
) -> str:
    """
    Build prompt for food recognition task with Chain-of-Thought reasoning.

    Chain-of-Thought improves accuracy by making the model analyze the image
    before generating JSON, reducing hallucinations.

    Args:
        user_comment: Optional user comment with food description and/or weights
        locale: Language locale for the prompt (default: "ru")

    Returns:
        Formatted prompt string for the LLM with CoT instructions
    """

    # Prepare user comment section
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
            weight_instruction = "\n⚠️ ВАЖНО: ПОЛЬЗОВАТЕЛЬ УКАЗАЛ ТОЧНЫЕ ВЕСА ПРОДУКТОВ — НЕ ИЗМЕНЯЙ ИХ БЕЗ ЯВНОГО ПРОТИВОРЕЧИЯ С ФОТО."

        base_prompt = f"""Ты — профессиональный диетолог-технолог. Твоя задача — точно оценить калорийность по фото.
{comment_section}{weight_instruction}

═══════════════════════════════════════════════════════════════
ШАГ 1: АНАЛИЗ (Chain-of-Thought Reasoning)
═══════════════════════════════════════════════════════════════

Сначала опиши свой мыслительный процесс на РУССКОМ языке:

1. **Визуальные признаки:** Что именно ты видишь на фото?
   - Какие продукты/блюда распознаёшь?
   - Цвет, текстура, форма каждого компонента

2. **Оценка размера и веса:**
   - Используй приборы/тарелку/руки как масштаб
   - Оцени геометрию порции (диаметр, высота, объём)
   - Сравни с типичными порциями этого блюда

3. **Обоснование веса:**
   - Почему именно такой вес (например, 300г, а не 500г)?
   - Какие признаки указывают на этот вес?
   - Есть ли сомнения в оценке?

4. **Проверка комментария:**
   - Соответствует ли фото комментарию пользователя?
   - Если пользователь указал веса, видны ли эти порции на фото?
   - Есть ли противоречия между фото и комментарием?

Начни свой анализ с метки ___ANALYSIS___ и закончи меткой ___ANALYSIS_END___

═══════════════════════════════════════════════════════════════
ШАГ 2: JSON (Strict Format)
═══════════════════════════════════════════════════════════════

После анализа выдай финальный результат в JSON формате.

⚠️ ЯЗЫКОВЫЕ ПРАВИЛА:
- ВСЕ названия блюд (name) — ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
- Даже если это "Hot Dog", пиши "Хот-дог"
- Даже если это "Burger", пиши "Бургер"
- НИКОГДА не используй английские слова в полях name и model_notes

ПРАВИЛА СОСТАВА (КРИТИЧЕСКИ ВАЖНО):

1. **Если комментарий ПУСТОЙ или содержит только название блюда:**
   - Верни ОДНО блюдо целиком
   - Примеры:
     * Фото бургера, комментарий пустой → "Чизбургер, 300г"
     * Комментарий "суп грибной" → "Суп грибной, 350г"
     * Комментарий "пицца" → "Пицца Маргарита, 400г"

2. **Если в комментарии перечислены ИНГРЕДИЕНТЫ:**
   - Верни каждый ингредиент ОТДЕЛЬНОЙ строкой в items
   - Примеры:
     * Комментарий "курица 150г, рис 200г" →
       items: [{{"name": "Куриная грудка", "grams": 150}}, {{"name": "Рис отварной", "grams": 200}}]
     * Комментарий "индейка, картофель, огурец" →
       items: [{{"name": "Индейка", "grams": ...}}, {{"name": "Картофель", "grams": ...}}, {{"name": "Огурец", "grams": ...}}]

ПРАВИЛА РАСЧЁТА ВЕСОВ:

Если в комментарии указаны веса (например: "индейка 150 г, картофель 200 г"):
1. Считай ЭТИ ВЕСА ОСНОВНЫМ ИСТОЧНИКОМ ПРАВДЫ
2. Используй фото только для проверки адекватности
3. НЕ МЕНЯЙ граммы из комментария, кроме явных противоречий
4. Если есть сомнения, сохрани исходные граммы и опиши сомнения в model_notes

Если в комментарии НЕТ весов:
- Используй свой анализ из ШАГ 1 для оценки весов
- Будь консервативен (лучше недооценить, чем переоценить)

Начни JSON-часть с метки ___JSON___ и выдай валидный JSON:

{{
  "items": [
    {{
      "name": "название продукта (РУССКИЙ язык)",
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
  "model_notes": "краткие комментарии (РУССКИЙ язык)"
}}

⚠️ КРИТИЧЕСКИ ВАЖНО:
1. Используй метки ___ANALYSIS___ и ___JSON___ для разделения частей
2. Все названия продуктов ТОЛЬКО на русском языке
3. JSON должен быть валидным (закрытые кавычки, без trailing commas)
4. Используй стандартные базы данных по питанию для расчёта КБЖУ"""

    else:  # English
        comment_section = f"""
=== USER COMMENT ===
{comment_text if comment_text else "No comment provided"}
====================
"""

        weight_instruction = ""
        if has_weights:
            weight_instruction = "\n⚠️ IMPORTANT: USER PROVIDED EXACT WEIGHTS — DO NOT CHANGE THEM WITHOUT EXPLICIT CONTRADICTION WITH THE PHOTO."

        base_prompt = f"""You are an expert in nutrition and portion weighing. You have:
1) A PHOTO of the dish.
2) A USER COMMENT with description and product weights.

First, CAREFULLY READ the comment, then look at the photo.
{comment_section}{weight_instruction}

RULES:

If the comment specifies weights and composition (e.g., "turkey 150 g, potatoes 200 g"):

1. Consider THESE WEIGHTS AND COMPOSITION as the PRIMARY SOURCE OF TRUTH.
2. Use the photo only to verify plausibility (is there actually turkey, potatoes, no completely different products).
3. DO NOT CHANGE the grams from the comment, except when they clearly contradict the image
   (e.g., "cucumber 50 g" is written, but the photo shows a huge pizza without cucumber).
4. If in doubt, you MUST keep the original grams from the comment and describe doubts in "model_notes".

If there are NO weights in the comment, but there is a description:
- Determine composition from comment + photo.
- Estimate weights from photo as realistically as possible.

If the comment is empty:
- Work from photo only.
- Identify all products in the image.
- Estimate weights as accurately as possible.

RESPONSE FORMAT — STRICTLY JSON without extra text:

{{
  "items": [
    {{
      "name": "product or dish name",
      "grams": number,         // weight in grams, float
      "kcal": number,          // calories
      "protein": number,       // protein (g)
      "fat": number,           // fat (g)
      "carbohydrates": number  // carbohydrates (g)
    }}
  ],
  "total": {{
    "kcal": number,
    "protein": number,
    "fat": number,
    "carbohydrates": number
  }},
  "model_notes": "brief comments on recognition, doubts, clarifications"
}}

CRITICALLY IMPORTANT:
- If the user specified concrete grams — use THEM, don't change.
- Don't add new products that are clearly not in the comment or photo.
- If NOT SURE about something, write about it in "model_notes", but don't break JSON structure.
- Don't use natural language comments outside the "model_notes" field.
- Response must be valid JSON (no comments, no extra text before or after JSON).
- Use standard nutrition databases for calculating calories and macros.

⚠️ CRITICAL — RESPONSE FORMAT:
1. Your response MUST be ONLY a JSON object.
2. NO markdown blocks (```json).
3. NO text before or after JSON.
4. NO natural language comments outside "model_notes" field.
5. Verify syntax: all strings closed with quotes, no trailing commas.

Start your response immediately with opening curly brace {{"""

    return base_prompt


def normalize_item_fields(item: dict) -> dict:
    """
    Normalize field names to match SSOT schema.

    LLM models may return alternative field names (e.g., "carbs" instead of "carbohydrates",
    "calories" instead of "kcal"). This function normalizes them to match our schema.

    Args:
        item: Raw item dict from AI response

    Returns:
        Normalized item dict with SSOT field names
    """
    # Create a copy to avoid mutating the original
    normalized = item.copy()

    # Normalize: carbs → carbohydrates
    if "carbs" in normalized and "carbohydrates" not in normalized:
        normalized["carbohydrates"] = normalized.pop("carbs")

    # Normalize: calories → kcal
    if "calories" in normalized and "kcal" not in normalized:
        normalized["kcal"] = normalized.pop("calories")

    return normalized


def parse_ai_response(response_text: str) -> tuple[List[FoodItem], Optional[str]]:
    """
    Parse AI model response into structured format with Chain-of-Thought support.

    Handles CoT format:
    - Ignores everything before ___JSON___ marker
    - Extracts JSON from after the marker
    - Uses json_repair for robust parsing

    Also handles:
    - Unterminated strings (connection cuts)
    - Missing closing braces/brackets
    - Markdown code blocks
    - Trailing commas
    """

    try:
        # Extract JSON part from Chain-of-Thought response
        json_text = response_text

        # Look for ___JSON___ separator
        if "___JSON___" in response_text:
            # Extract everything after ___JSON___
            parts = response_text.split("___JSON___", 1)
            json_text = parts[1].strip()
            logger.debug("Found ___JSON___ separator, extracted JSON part")
        else:
            # Fallback: try to find first { (for backward compatibility)
            logger.debug("No ___JSON___ separator found, using full response")

        # Use json_repair to extract and fix JSON
        # This handles unterminated strings, missing braces, markdown blocks, etc.
        data = repair_json(json_text, return_objects=True)

        # Extract items
        items = []
        for item_data in data.get("items", []):
            # Normalize field names before creating FoodItem
            normalized_item = normalize_item_fields(item_data)

            items.append(
                FoodItem(
                    name=normalized_item["name"],
                    grams=float(normalized_item["grams"]),
                    kcal=float(normalized_item["kcal"]),
                    protein=float(normalized_item["protein"]),
                    fat=float(normalized_item["fat"]),
                    carbohydrates=float(normalized_item["carbohydrates"]),
                )
            )

        model_notes = data.get("model_notes")

        return items, model_notes

    except KeyError as e:
        logger.error(f"Missing required field in AI response: {e}")
        raise OpenRouterError(f"Missing required field in AI response: {e}")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid data type in AI response: {e}")
        raise OpenRouterError(f"Invalid data type in AI response: {e}")


async def _make_openrouter_request(
    client: httpx.AsyncClient, url: str, headers: dict, payload: dict
) -> httpx.Response:
    """
    Make a single request to OpenRouter with retry logic.

    Implements exponential backoff for retryable errors (429, 5xx, timeout).
    Does NOT retry for non-retryable errors (400, 401, 403, 413, 422).
    """
    last_exception = None

    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            response = await client.post(url, headers=headers, json=payload)

            # Check if we should retry based on status code
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < RETRY_MAX_ATTEMPTS:
                    delay = min(
                        RETRY_INITIAL_DELAY
                        * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                        RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        f"OpenRouter returned {response.status_code}, "
                        f"retrying in {delay:.1f}s (attempt {attempt}/{RETRY_MAX_ATTEMPTS})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Last attempt failed, return the response
                    logger.error(
                        f"OpenRouter returned {response.status_code} after "
                        f"{RETRY_MAX_ATTEMPTS} attempts"
                    )
                    return response

            # Non-retryable status or success - return immediately
            return response

        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < RETRY_MAX_ATTEMPTS:
                delay = min(
                    RETRY_INITIAL_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                    RETRY_MAX_DELAY,
                )
                logger.warning(
                    f"OpenRouter request timed out, "
                    f"retrying in {delay:.1f}s (attempt {attempt}/{RETRY_MAX_ATTEMPTS})"
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"OpenRouter request timed out after {RETRY_MAX_ATTEMPTS} attempts"
                )
                raise

        except httpx.RequestError as e:
            # Network errors - retry
            last_exception = e
            if attempt < RETRY_MAX_ATTEMPTS:
                delay = min(
                    RETRY_INITIAL_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                    RETRY_MAX_DELAY,
                )
                logger.warning(
                    f"OpenRouter request failed ({type(e).__name__}), "
                    f"retrying in {delay:.1f}s (attempt {attempt}/{RETRY_MAX_ATTEMPTS})"
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"OpenRouter request failed after {RETRY_MAX_ATTEMPTS} attempts: {e}"
                )
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise OpenRouterError("Unexpected retry loop exit")


async def recognize_food_with_bytes(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru",
) -> tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    """
    Call OpenRouter API to recognize food in image and return nutritional info.

    Uses json_repair + native JSON mode for reliable parsing (no retry loop needed).

    Args:
        image_bytes: Raw image file bytes
        filename: Original filename (for logging)
        content_type: MIME type of the image (e.g., "image/jpeg")
        user_comment: Optional user comment about the food
        locale: Language locale for the prompt (default: "ru")

    Returns:
        Tuple of (food_items, total_nutrition, model_notes)

    Raises:
        OpenRouterError: If API call fails or response is invalid
    """

    # Convert bytes to base64 data URL
    b64_image = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64_image}"

    logger.debug(f"Converted image to base64 data URL (length: {len(data_url)} chars)")

    try:
        # Build prompt
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
                    f"OpenRouter API error: {response.status_code} - {error_detail}"
                )
                raise OpenRouterError(
                    f"OpenRouter API returned {response.status_code}: {error_detail}"
                )

            result = response.json()

            # Log token usage if available
            usage = result.get("usage")
            if usage:
                logger.info(
                    f"OpenRouter token usage: "
                    f"prompt={usage.get('prompt_tokens', 'N/A')}, "
                    f"completion={usage.get('completion_tokens', 'N/A')}, "
                    f"total={usage.get('total_tokens', 'N/A')}"
                )

            # Extract AI response text
            ai_response_text = result["choices"][0]["message"]["content"]

            # Parse the response (json_repair handles all edge cases)
            items, model_notes = parse_ai_response(ai_response_text)

            # Calculate totals
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
        logger.error(f"OpenRouter API request failed: {e}")
        raise OpenRouterError(f"Failed to connect to OpenRouter API: {e}")
    except KeyError as e:
        logger.error(f"Unexpected response structure from OpenRouter: {e}")
        raise OpenRouterError(f"Unexpected response structure from OpenRouter: {e}")
    except OpenRouterError:
        # Re-raise OpenRouterError (from parse_ai_response or other places)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in recognize_food_with_bytes: {e}", exc_info=True)
        raise OpenRouterError(f"Unexpected error: {e}")
