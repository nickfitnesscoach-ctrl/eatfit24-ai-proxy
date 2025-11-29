# EatFit24 AI Proxy

Микросервис, который принимает фото еды (по URL) и опциональный комментарий пользователя,
вызывает внешнюю AI-модель (OpenRouter) и возвращает структуру с продуктами и КБЖУ.

## Стек
- Python 3.12+
- FastAPI
- Uvicorn
- httpx

## Быстрый старт

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Эндпоинты

**GET /health** — проверка состояния.

**POST /api/v1/ai/recognize-food** — основной AI-эндпоинт.

### Пример запроса

```bash
curl -X POST http://127.0.0.1:8001/api/v1/ai/recognize-food \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/food.jpg",
    "user_comment": "Это гречка с курицей",
    "locale": "ru"
  }'
```

### Пример ответа

```json
{
  "items": [
    {
      "name": "Гречка отварная",
      "grams": 150.0,
      "kcal": 165.0,
      "protein": 6.0,
      "fat": 1.5,
      "carbs": 30.0
    },
    {
      "name": "Куриная грудка",
      "grams": 100.0,
      "kcal": 165.0,
      "protein": 31.0,
      "fat": 3.6,
      "carbs": 0.0
    }
  ],
  "total": {
    "kcal": 330.0,
    "protein": 37.0,
    "fat": 5.1,
    "carbs": 30.0
  },
  "model_notes": "Распознано на основе изображения и комментария пользователя"
}
```

## Переменные окружения

Создайте файл `.env` на основе `.env.example`:

```
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

## Разработка

Сервер автоматически перезагружается при изменении кода благодаря флагу `--reload`.
