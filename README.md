# EatFit24 AI Proxy

Микросервис для распознавания еды по фотографии. Принимает изображение и комментарий пользователя,
вызывает AI-модель через OpenRouter и возвращает структурированные данные о продуктах и КБЖУ.

## Что делает сервис

- **Распознаёт еду на фото** — определяет продукты и блюда
- **Считает КБЖУ** — калории, белки, жиры, углеводы
- **Учитывает комментарии** — если пользователь указал веса, AI использует их
- **Поддерживает два языка** — русский (по умолчанию) и английский

## Архитектурная позиция

> AI Proxy — это **stateless внутренний микросервис**.  
> Он **не реализует** пользовательские лимиты и биллинг.  
> Все бизнес-квоты и правила ценообразования — **на стороне backend**.

## Быстрый старт (локально)

```bash
cd eatfit24-ai-proxy

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Заполните .env — обязательные переменные:
# - OPENROUTER_API_KEY
# - OPENROUTER_MODEL
# - API_PROXY_SECRET

uvicorn app.main:app --reload --port 8001
Переменные окружения
⚠️ Обязательные переменные должны быть заданы, иначе сервис не запустится.

Переменная	Обязательна	Описание
OPENROUTER_API_KEY	✅	API ключ OpenRouter
OPENROUTER_MODEL	✅	Модель (например openai/gpt-4o-mini)
OPENROUTER_BASE_URL	❌	Base URL OpenRouter (default: https://openrouter.ai/api/v1)
API_PROXY_SECRET	✅	Ключ для аутентификации запросов (header X-API-Key)
LOG_LEVEL	❌	Уровень логов (default: INFO)
MAX_IMAGE_SIZE_BYTES	❌	Макс. размер файла в байтах (default: 5MB)

Примеры запросов
Health Check
bash
Копировать код
curl http://localhost:8001/health
# {"status":"ok"}
Распознавание еды
bash
Копировать код
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: ваш_ключ" \
  -F "image=@food.jpg" \
  -F "user_comment=Индейка 150 г, картофель 200 г" \
  -F "locale=ru"
Пример ответа
SSOT-поля: grams, kcal, carbohydrates
Для совместимости также добавляются алиасы: amount_grams, calories, carbs

json
Копировать код
{
  "items": [
    {
      "name": "Индейка",
      "grams": 150.0,
      "amount_grams": 150.0,
      "kcal": 180.0,
      "calories": 180.0,
      "protein": 30.0,
      "fat": 6.0,
      "carbohydrates": 0.0,
      "carbs": 0.0
    },
    {
      "name": "Картофель отварной",
      "grams": 200.0,
      "amount_grams": 200.0,
      "kcal": 160.0,
      "calories": 160.0,
      "protein": 4.0,
      "fat": 0.2,
      "carbohydrates": 36.0,
      "carbs": 36.0
    }
  ],
  "total": {
    "kcal": 340.0,
    "calories": 340.0,
    "protein": 34.0,
    "fat": 6.2,
    "carbohydrates": 36.0,
    "carbs": 36.0
  },
  "model_notes": "Веса взяты из комментария пользователя"
}
Docker
Локальный запуск
bash
Копировать код
cp .env.example .env
# Заполните .env

docker compose up -d --build
docker compose ps
docker logs -f eatfit24-ai-proxy

docker compose down
На сервере
bash
Копировать код
# Deploy происходит автоматически через GitHub Actions при push в master
# Или вручную:
git pull && docker compose up -d --build
Troubleshooting
Сервис не запускается
csharp
Копировать код
pydantic ValidationError: Field required
Причина: Не заданы обязательные переменные окружения.
Решение: Проверьте .env — должны быть OPENROUTER_API_KEY, OPENROUTER_MODEL, API_PROXY_SECRET.

401 Unauthorized
Причина: Неверный или отсутствующий API ключ.
Решение: Проверьте заголовок X-API-Key, он должен совпадать с API_PROXY_SECRET.

429 Too Many Requests
Причина: Превышен лимит запросов к OpenRouter.
Что происходит: Сервис автоматически делает несколько попыток с backoff.
Решение: Подождите или проверьте лимиты в OpenRouter.

500 AI Service Error (timeout)
Причина: OpenRouter не ответил за таймаут.
Решение: Повторите запрос. Если повторяется — проверьте статус OpenRouter/модель/ключ.

413 File Too Large
Причина: Изображение больше лимита.
Решение: Уменьшите размер изображения перед отправкой или увеличьте MAX_IMAGE_SIZE_BYTES.

Безопасность
✅ API key аутентификация (timing-safe compare)

✅ Контейнер работает от non-root пользователя

✅ Resource limits в Docker

✅ Никаких секретов в git (.env в .gitignore)

✅ Логи в JSON + request_id (ответ содержит X-Request-ID)

yaml
Копировать код

---

## Важно: чтобы README про `MAX_IMAGE_SIZE_BYTES` работал на 100%
В `config.py` лучше явно проставить алиасы env-переменных (иначе можно поймать “не читает переменную”).  
Если хочешь, я перепишу `config.py` ещё раз в точном стиле:

```python
max_image_size_bytes: int = Field(
    default=5 * 1024 * 1024,
    validation_alias="MAX_IMAGE_SIZE_BYTES",
)
и аналогично для OPENROUTER_*, API_PROXY_SECRET, LOG_LEVEL.