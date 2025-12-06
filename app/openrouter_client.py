import json
import base64
import logging
import re
from typing import Optional, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from app.schemas import FoodItem, TotalNutrition

logger = logging.getLogger(__name__)

# Pattern to detect explicit weights in user comments (e.g., "150 г", "200 g")
GRAMS_PATTERN = re.compile(r"\b\d+\s*(г|гр|g)\b", re.IGNORECASE)


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


def build_food_recognition_prompt(user_comment: Optional[str] = None, locale: str = "ru") -> str:
    """
    Build prompt for food recognition task with weight prioritization

    Args:
        user_comment: Optional user comment with food description and/or weights
        locale: Language locale for the prompt (default: "ru")

    Returns:
        Formatted prompt string for the LLM
    """

    # Prepare user comment section
    comment_text = user_comment.strip() if user_comment and user_comment.strip() else None
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

        base_prompt = f"""Ты — эксперт по питанию и взвешиванию порций. У тебя есть:
1) ФОТО блюда.
2) КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ с описанием и весами продуктов.

Сначала ВНИМАТЕЛЬНО ПРОЧИТАЙ комментарий, потом смотри на фото.
{comment_section}{weight_instruction}

ПРАВИЛА РАБОТЫ:

Если в комментарии указаны веса и состав (например: "индейка 150 г, картофель 200 г"):

1. Считай ЭТИ ВЕСА И СОСТАВ ОСНОВНЫМ ИСТОЧНИКОМ ПРАВДЫ.
2. Используй фото только для проверки адекватности (есть ли реально индейка, картофель, нет ли совсем других продуктов).
3. НЕ МЕНЯЙ граммы из комментария, кроме случаев, когда они явно противоречат изображению
   (например, написано "огурец 50 г", а на фото огромная пицца без огурца).
4. Если есть сомнения, ОБЯЗАТЕЛЬНО сохрани исходные граммы из комментария и опиши сомнения в "model_notes".

Если в комментарии НЕТ весов, но есть описание:
- Определи состав по комментарию + фото.
- Оцени веса по фото максимально реалистично.

Если комментарий пустой:
- Работай только по фото.
- Определи все продукты на изображении.
- Оцени веса максимально точно.

ФОРМАТ ОТВЕТА — СТРОГО JSON без лишнего текста:

{{
  "items": [
    {{
      "name": "название продукта или блюда",
      "grams": число,          // вес в граммах, float
      "kcal": число,           // калории
      "protein": число,        // белки (г)
      "fat": число,            // жиры (г)
      "carbs": число           // углеводы (г)
    }}
  ],
  "total": {{
    "kcal": число,
    "protein": число,
    "fat": число,
    "carbs": число
  }},
  "model_notes": "краткие комментарии к распознаванию, сомнения, уточнения"
}}

КРИТИЧЕСКИ ВАЖНО:
- Если пользователь написал конкретные граммы — используй ИХ, не меняй.
- Не добавляй новые продукты, которых явно нет ни в комментарии, ни на фото.
- Если в чём-то НЕ УВЕРЕН, напиши об этом в "model_notes", но JSON-структуру не ломай.
- Не используй комментарии на естественном языке вне поля "model_notes".
- Ответ должен быть валидным JSON (без комментариев, без лишнего текста до или после JSON).
- Используй стандартные базы данных по питанию для расчёта КБЖУ."""

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
      "carbs": number          // carbohydrates (g)
    }}
  ],
  "total": {{
    "kcal": number,
    "protein": number,
    "fat": number,
    "carbs": number
  }},
  "model_notes": "brief comments on recognition, doubts, clarifications"
}}

CRITICALLY IMPORTANT:
- If the user specified concrete grams — use THEM, don't change.
- Don't add new products that are clearly not in the comment or photo.
- If NOT SURE about something, write about it in "model_notes", but don't break JSON structure.
- Don't use natural language comments outside the "model_notes" field.
- Response must be valid JSON (no comments, no extra text before or after JSON).
- Use standard nutrition databases for calculating calories and macros."""

    return base_prompt


def parse_ai_response(response_text: str) -> tuple[List[FoodItem], Optional[str]]:
    """Parse AI model response into structured format"""

    try:
        # Try to extract JSON from response
        # Sometimes models wrap JSON in markdown code blocks
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Parse JSON
        data = json.loads(text)

        # Extract items
        items = []
        for item_data in data.get("items", []):
            items.append(FoodItem(
                name=item_data["name"],
                grams=float(item_data["grams"]),
                kcal=float(item_data["kcal"]),
                protein=float(item_data["protein"]),
                fat=float(item_data["fat"]),
                # F-004 FIX: Accept both carbs and carbohydrates from AI response
                carbohydrates=float(item_data.get("carbs", item_data.get("carbohydrates", 0)))
            ))

        model_notes = data.get("model_notes")

        return items, model_notes

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise OpenRouterError(f"Invalid JSON response from AI model: {e}")
    except KeyError as e:
        logger.error(f"Missing required field in AI response: {e}")
        raise OpenRouterError(f"Missing required field in AI response: {e}")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid data type in AI response: {e}")
        raise OpenRouterError(f"Invalid data type in AI response: {e}")


# A-002 FIX: Add retry decorator for transient failures
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.RequestError)),
    reraise=True
)
async def recognize_food_with_bytes(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru"
) -> tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    """
    Call OpenRouter API to recognize food in image and return nutritional info

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

    prompt = build_food_recognition_prompt(user_comment, locale)

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://eatfit24.com",
        "X-Title": "EatFit24"
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }
        ]
    }

    try:
        # A-001 FIX: Reduced timeout from 60s to 30s for better UX
        # Users typically won't wait longer than 30 seconds for recognition
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"OpenRouter API error: {response.status_code} - {error_detail}")
                raise OpenRouterError(f"OpenRouter API returned {response.status_code}: {error_detail}")

            result = response.json()

            # Extract AI response text
            ai_response_text = result["choices"][0]["message"]["content"]

            # Parse the response
            items, model_notes = parse_ai_response(ai_response_text)

            # Calculate totals
            total = TotalNutrition(
                kcal=sum(item.kcal for item in items),
                protein=sum(item.protein for item in items),
                fat=sum(item.fat for item in items),
                carbohydrates=sum(item.carbohydrates for item in items)
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
