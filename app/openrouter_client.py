import json
import logging
from typing import Optional, List
import httpx
from app.config import settings
from app.schemas import FoodItem, TotalNutrition

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""
    pass


def build_food_recognition_prompt(image_url: str, user_comment: Optional[str] = None, locale: str = "ru") -> str:
    """Build prompt for food recognition task"""

    base_prompt = """Analyze the food image and return a JSON response with the following structure:
{
  "items": [
    {
      "name": "food name",
      "grams": weight in grams,
      "kcal": calories,
      "protein": protein in grams,
      "fat": fat in grams,
      "carbs": carbohydrates in grams
    }
  ],
  "model_notes": "any additional notes or warnings"
}

Important:
- Identify all food items visible in the image
- Estimate weight in grams as accurately as possible
- Calculate nutritional values (kcal, protein, fat, carbs) per item
- Use standard nutritional databases for calculations
- Sum up all items to get totals
- Be precise and realistic with portion sizes"""

    if locale == "ru":
        base_prompt = """Проанализируй изображение еды и верни JSON-ответ следующей структуры:
{
  "items": [
    {
      "name": "название блюда",
      "grams": вес в граммах,
      "kcal": калории,
      "protein": белки в граммах,
      "fat": жиры в граммах,
      "carbs": углеводы в граммах
    }
  ],
  "model_notes": "любые дополнительные заметки или предупреждения"
}

Важно:
- Определи все продукты, видимые на изображении
- Оцени вес в граммах максимально точно
- Рассчитай пищевую ценность (ккал, белки, жиры, углеводы) для каждого продукта
- Используй стандартные базы данных по питанию
- Суммируй все продукты для получения итогов
- Будь точен и реалистичен с размерами порций"""

    if user_comment:
        base_prompt += f"\n\nUser comment: {user_comment}"

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
                carbs=float(item_data["carbs"])
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


async def recognize_food_with_openrouter(
    image_url: str,
    user_comment: Optional[str] = None,
    locale: str = "ru"
) -> tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    """
    Call OpenRouter API to recognize food in image and return nutritional info

    Args:
        image_url: URL of the food image
        user_comment: Optional user comment about the food
        locale: Language locale for the prompt (default: "ru")

    Returns:
        Tuple of (food_items, total_nutrition, model_notes)

    Raises:
        OpenRouterError: If API call fails or response is invalid
    """

    prompt = build_food_recognition_prompt(image_url, user_comment, locale)

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
                            "url": str(image_url)
                        }
                    }
                ]
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                carbs=sum(item.carbs for item in items)
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
