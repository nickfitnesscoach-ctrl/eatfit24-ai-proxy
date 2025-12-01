# EatFit24 AI Proxy

Микросервис, который принимает фото еды (файл изображения) и опциональный комментарий пользователя,
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
  -H "X-API-Key: your_api_key_here" \
  -F "image=@/path/to/food-photo.jpg" \
  -F "user_comment=Это гречка с курицей" \
  -F "locale=ru"
```

**Важно**: API принимает только `multipart/form-data` с файлом изображения (JPEG/PNG, макс. 5 МБ).

### Приоритизация весов из комментария

Если в комментарии пользователя указаны конкретные веса (например, "Индейка 150 г, картофель 200 г"),
AI будет использовать эти веса как основной источник правды, а фото — только для проверки адекватности.

**Пример с весами:**
```bash
curl -X POST http://127.0.0.1:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: your_api_key_here" \
  -F "image=@food.jpg" \
  -F "user_comment=Индейка 150 г, картофель 200 г" \
  -F "locale=ru"
```

В этом случае модель сохранит указанные граммы (150 и 200) и не будет их менять на основе визуальной оценки,
если только они не противоречат изображению явным образом.

Подробнее: см. [docs/WEIGHT_PRIORITIZATION.md](docs/WEIGHT_PRIORITIZATION.md)

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
OPENROUTER_MODEL=openai/gpt-5-image-mini
API_PROXY_SECRET=your_secret_key_here
MAX_IMAGE_SIZE_BYTES=5242880  # 5 MB (опционально)
```

## Docker

### Локальный запуск

```bash
# Создайте .env файл
cp .env.example .env
# Отредактируйте .env и добавьте ваши ключи

# Запустите контейнер
docker compose up -d --build

# Проверьте статус
docker compose ps
docker logs eatfit24-ai-proxy

# Остановите контейнер
docker compose down
```

### Деплой на сервер

Проект автоматически деплоится на NL-сервер при каждом push в `master` ветку через GitHub Actions.

Подробная информация о деплое: см. [DEPLOYMENT.md](DEPLOYMENT.md)

## API Documentation

Полная документация API для интеграции с Django backend: см. [API_DOCS.md](API_DOCS.md)

## Разработка

Сервер автоматически перезагружается при изменении кода благодаря флагу `--reload`.

## Безопасность

- Доступ ограничен через Tailscale VPN (100.0.0.0/8)
- API key аутентификация через X-API-Key header
- Firewall настроен на блокировку внешнего доступа
- Все запросы логируются с IP адресами и timing информацией
