# API Contract — EatFit24 AI Proxy

**SSOT (Single Source of Truth):** [`app/schemas.py`](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/eatfit24-ai-proxy/app/schemas.py)

---

## Endpoints

### GET /health

Health check endpoint. No authentication required.

**Response:**
```json
{"status": "ok"}
```

---

### POST /api/v1/ai/recognize-food

Analyze a food image and return nutritional information.

**Content-Type:** `multipart/form-data`

**Authentication:** Required (X-API-Key header)

#### Request Fields

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `image` | File | ✅ | JPEG/PNG, max 5MB | Food image file |
| `user_comment` | string | ❌ | None | User's comment about food (weights, composition) |
| `locale` | string | ❌ | Default: "ru" | Language locale (ru/en) |

#### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | ✅ | Authentication key (matches `API_PROXY_SECRET` env) |
| `X-Request-ID` | ❌ | Optional correlation ID (will be echoed in response) |

#### Response Schema (200 OK)

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
    }
  ],
  "total": {
    "kcal": 165.0,
    "protein": 31.0,
    "fat": 3.6,
    "carbs": 0.0
  },
  "model_notes": "Распознано на основе изображения"
}
```

#### Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Request correlation ID (from request or generated) |

---

## Error Reference

| Code | HTTP Status | Message | Retryable | Client Action |
|------|-------------|---------|-----------|---------------|
| `INVALID_FILE_TYPE` | 400 | Unsupported file type: {type}. Only JPEG/PNG are allowed. | ❌ | Use JPEG or PNG format |
| `EMPTY_FILE` | 400 | Empty file. | ❌ | Upload a valid file |
| `FILE_TOO_LARGE` | 413 | File too large. Max allowed size is {bytes} bytes ({MB} MB). | ❌ | Reduce file size |
| `INVALID_API_KEY` | 401 | Invalid or missing API key | ❌ | Check API key |
| `VALIDATION_ERROR` | 422 | Field required / validation error | ❌ | Fix request format |
| `AI_SERVICE_ERROR` | 500 | AI service error: {details} | ✅ | Retry after 5-30 seconds |
| `INTERNAL_ERROR` | 500 | Internal server error: {details} | ⚠️ | Retry with caution |

### Retry Semantics

- **429 / 5xx from OpenRouter**: Service retries automatically (3 attempts, exponential backoff)
- **5xx returned to client**: Retry after 5-30 seconds
- **4xx**: Never retry without fixing the request

> 💡 **Idempotency:** AI Proxy is stateless and idempotent per request. Clients MAY safely retry failed requests.

---

## Data Models

### FoodItem

```python
class FoodItem(BaseModel):
    name: str        # Product/dish name
    grams: float     # Weight in grams
    kcal: float      # Calories
    protein: float   # Protein in grams
    fat: float       # Fat in grams
    carbs: float     # Carbohydrates in grams
```

### TotalNutrition

```python
class TotalNutrition(BaseModel):
    kcal: float      # Total calories
    protein: float   # Total protein
    fat: float       # Total fat
    carbs: float     # Total carbohydrates
```

### RecognizeFoodResponse

```python
class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]       # Recognized food items
    total: TotalNutrition       # Sum of all items
    model_notes: Optional[str]  # AI model notes/comments
```

---

## cURL Examples

### Health Check
```bash
curl http://localhost:8001/health
```

### Recognize Food
```bash
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: your_api_key_here" \
  -F "image=@/path/to/food-photo.jpg" \
  -F "user_comment=Индейка 150 г, картофель 200 г" \
  -F "locale=ru"
```

### With Request ID
```bash
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: your_api_key_here" \
  -H "X-Request-ID: my-request-123" \
  -F "image=@food.jpg"
```
