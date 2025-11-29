# EatFit24 AI Proxy API Documentation

## Base URL
- **Production**: `http://100.84.210.65:8001` (Tailscale network only)
- **Development**: `http://localhost:8001`

## Authentication
All API requests (except `/health`) require authentication using an API key.

### Header
```
X-API-Key: <your_api_key>
```

The API key is configured via the `API_PROXY_SECRET` environment variable.

## Endpoints

### 1. Health Check
Check if the service is running.

**Endpoint**: `GET /health`

**Authentication**: Not required

**Response**:
```json
{
  "status": "ok"
}
```

---

### 2. Recognize Food
Analyze a food image and return nutritional information.

**Endpoint**: `POST /api/v1/ai/recognize-food`

**Authentication**: Required (X-API-Key header)

**Request Body**:
```json
{
  "image_url": "https://example.com/food-image.jpg",
  "user_comment": "Grilled chicken with rice",  // optional
  "locale": "ru"  // optional, default: "ru"
}
```

**Request Fields**:
- `image_url` (string, required): URL of the food image to analyze
- `user_comment` (string, optional): Additional context about the food. If not provided, the model analyzes only the image content.
- `locale` (string, optional): Language for response (e.g., "ru", "en"). Default: "ru"

**Response** (200 OK):
```json
{
  "items": [
    {
      "food_name_ru": "Куриная грудка гриль",
      "food_name_en": "Grilled Chicken Breast",
      "portion_weight_g": 150.0,
      "calories": 165,
      "protein_g": 31.0,
      "fat_g": 3.6,
      "carbs_g": 0.0
    },
    {
      "food_name_ru": "Рис белый отварной",
      "food_name_en": "Cooked White Rice",
      "portion_weight_g": 200.0,
      "calories": 260,
      "protein_g": 5.4,
      "fat_g": 0.6,
      "carbs_g": 56.0
    }
  ],
  "total": {
    "calories": 425,
    "protein_g": 36.4,
    "fat_g": 4.2,
    "carbs_g": 56.0
  },
  "model_notes": "High protein meal, low fat"  // optional
}
```

**Error Responses**:

- **401 Unauthorized**: Invalid or missing API key
```json
{
  "detail": "Invalid or missing API key"
}
```

- **422 Validation Error**: Invalid request body
```json
{
  "detail": [
    {
      "loc": ["body", "image_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

- **500 Internal Server Error**: AI service error or server error
```json
{
  "detail": "AI service error: <error message>"
}
```

---

## Integration Example (Django/Python)

```python
import requests

API_URL = "http://100.84.210.65:8001"
API_KEY = "your_api_key_here"

def recognize_food(image_url: str, user_comment: str = None, locale: str = "ru"):
    """
    Call the AI Proxy to recognize food in an image

    Args:
        image_url: URL of the food image
        user_comment: Optional comment about the food. If not provided, only image is analyzed.
        locale: Language code (default: "ru")

    Returns:
        dict: Response with recognized food items and totals
    """
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "image_url": image_url,
        "locale": locale
    }

    if user_comment:
        payload["user_comment"] = user_comment

    response = requests.post(
        f"{API_URL}/api/v1/ai/recognize-food",
        json=payload,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


# Example usage
try:
    result = recognize_food(
        image_url="https://example.com/food.jpg",
        user_comment="Breakfast",
        locale="ru"
    )

    print(f"Total calories: {result['total']['calories']}")
    print(f"Items found: {len(result['items'])}")

    for item in result['items']:
        print(f"- {item['food_name_ru']}: {item['calories']} kcal")

except requests.exceptions.HTTPError as e:
    print(f"API Error: {e.response.status_code} - {e.response.text}")
except Exception as e:
    print(f"Error: {str(e)}")
```

---

## Notes

- **This API is internal and must not be exposed to the public internet**. Access is restricted via Tailscale VPN + API key authentication.
- The service is only accessible within the Tailscale VPN network (100.0.0.0/8)
- All requests are logged with timing information for monitoring and debugging
- Images should be publicly accessible URLs (HTTPS recommended)
- Recommended timeout: 30 seconds (AI processing may take time)
- Maximum image size is determined by the AI model limits
- Default locale is "ru" for Russian-speaking users. Use "en" for English responses.
