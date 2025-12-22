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

**Content-Type**: `multipart/form-data`

**Request Fields**:
- `image` (file, required): Food image file (JPEG or PNG format, max 5 MB)
- `user_comment` (string, optional): Additional context about the food. If not provided, the model analyzes only the image content.
- `locale` (string, optional): Language for response (e.g., "ru", "en"). Default: "ru"

**cURL Example**:
```bash
curl -X POST http://100.84.210.65:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: your_api_key_here" \
  -F "image=@/path/to/food-photo.jpg" \
  -F "user_comment=Grilled chicken with rice" \
  -F "locale=ru"
```

**Response** (200 OK):
```json
{
  "items": [
    {
      "name": "Куриная грудка гриль",
      "grams": 150.0,
      "kcal": 165.0,
      "protein": 31.0,
      "fat": 3.6,
      "carbs": 0.0
    },
    {
      "name": "Рис белый отварной",
      "grams": 200.0,
      "kcal": 260.0,
      "protein": 5.4,
      "fat": 0.6,
      "carbs": 56.0
    }
  ],
  "total": {
    "kcal": 425.0,
    "protein": 36.4,
    "fat": 4.2,
    "carbs": 56.0
  },
  "model_notes": "High protein meal, low fat"
}
```

**Response Headers**:
- `X-Request-ID`: Request correlation ID (echoed from request or generated)

**Error Responses**:

- **400 Bad Request**: Invalid file type or empty file
```json
{
  "detail": "Unsupported file type: image/gif. Only JPEG/PNG are allowed."
}
```
or
```json
{
  "detail": "Empty file."
}
```

- **401 Unauthorized**: Invalid or missing API key
```json
{
  "detail": "Invalid or missing API key"
}
```

- **413 Payload Too Large**: File exceeds maximum size limit (5 MB)
```json
{
  "detail": "File too large. Max allowed size is 5242880 bytes (5 MB)."
}
```

- **422 Validation Error**: Missing required fields
```json
{
  "detail": [
    {
      "loc": ["body", "image"],
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

def recognize_food(image_path: str, user_comment: str = None, locale: str = "ru"):
    """
    Call the AI Proxy to recognize food in an image

    Args:
        image_path: Path to the local image file
        user_comment: Optional comment about the food. If not provided, only image is analyzed.
        locale: Language code (default: "ru")

    Returns:
        dict: Response with recognized food items and totals
    """
    headers = {
        "X-API-Key": API_KEY
    }

    # Prepare multipart form data
    files = {
        "image": open(image_path, "rb")
    }

    data = {
        "locale": locale
    }

    if user_comment:
        data["user_comment"] = user_comment

    response = requests.post(
        f"{API_URL}/api/v1/ai/recognize-food",
        files=files,
        data=data,
        headers=headers,
        timeout=60
    )

    response.raise_for_status()
    return response.json()


# Example usage
try:
    result = recognize_food(
        image_path="/path/to/food-photo.jpg",
        user_comment="Breakfast",
        locale="ru"
    )

    print(f"Total kcal: {result['total']['kcal']}")
    print(f"Items found: {len(result['items'])}")

    for item in result['items']:
        print(f"- {item['name']}: {item['kcal']} kcal")

except requests.exceptions.HTTPError as e:
    print(f"API Error: {e.response.status_code} - {e.response.text}")
except Exception as e:
    print(f"Error: {str(e)}")
```

### Integration with Django (File Upload from Request)

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import requests

API_URL = "http://100.84.210.65:8001"
API_KEY = "your_api_key_here"

@require_http_methods(["POST"])
def analyze_food(request):
    """
    Django view to handle food image upload and analysis
    """
    if 'image' not in request.FILES:
        return JsonResponse({"error": "No image file provided"}, status=400)

    image_file = request.FILES['image']
    user_comment = request.POST.get('user_comment', '')
    locale = request.POST.get('locale', 'ru')

    headers = {
        "X-API-Key": API_KEY
    }

    files = {
        "image": (image_file.name, image_file.read(), image_file.content_type)
    }

    data = {
        "locale": locale
    }

    if user_comment:
        data["user_comment"] = user_comment

    try:
        response = requests.post(
            f"{API_URL}/api/v1/ai/recognize-food",
            files=files,
            data=data,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()
        return JsonResponse(response.json())

    except requests.exceptions.HTTPError as e:
        return JsonResponse({
            "error": f"AI Proxy error: {e.response.status_code}",
            "detail": e.response.text
        }, status=e.response.status_code)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
```

---

## Notes

- **This API is internal and must not be exposed to the public internet**. Access is restricted via Tailscale VPN + API key authentication.
- The service is only accessible within the Tailscale VPN network (100.0.0.0/8)
- All requests are logged with timing information for monitoring and debugging (image content is NOT logged for privacy)
- **Maximum file size**: 5 MB (configurable via `MAX_IMAGE_SIZE_BYTES` environment variable)
- **Supported formats**: JPEG, PNG only
- **Recommended timeout**: 60 seconds (AI processing may take time for large images)
- Default locale is "ru" for Russian-speaking users. Use "en" for English responses.
- The API no longer accepts JSON requests with `image_url` - only `multipart/form-data` with file uploads
