# Инструкция по деплою версии 1.2.0

## Что исправлено

Версия 1.2.0 исправляет критическую проблему с ошибками `Unterminated string` и `500 ERROR` при обрыве JSON-ответов от AI моделей.

## Изменения

1. **json-repair** — автоматическое исправление неполных JSON
2. **Native JSON mode** — принудительный валидный JSON от модели
3. **Оптимизированные retry** — быстрее отдаём ошибки пользователю

## Шаги деплоя

### Вариант 1: Автоматический (через Git)

```bash
# На сервере
cd eatfit24-ai-proxy
git pull origin master
docker compose down
docker compose up -d --build

# Проверка
curl http://localhost:8001/health
# Expected: {"status":"ok"}

docker compose logs -f
# Проверить, что нет ошибок при старте
```

### Вариант 2: Локальное тестирование перед деплоем

```bash
# Локально
pip install -r requirements.txt

# Проверка синтаксиса
python -m py_compile app/openrouter_client.py

# Запуск
uvicorn app.main:app --reload --port 8001

# Тестирование
python tests/test_api.py
```

### Вариант 3: Docker локально

```bash
docker compose down
docker compose up -d --build
docker compose logs -f

# Тест
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_PROXY_SECRET" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "locale=ru"
```

## Проверка после деплоя

### 1. Health Check
```bash
curl http://localhost:8001/health
# {"status":"ok"}
```

### 2. Logs Check
```bash
docker compose logs --tail=50

# Проверить:
# - Нет ошибок импорта json_repair
# - Сервис запустился успешно
# - Формат логов JSON
```

### 3. Functional Test
```bash
python tests/test_api.py

# Должно пройти без 500 ошибок
# Даже если AI вернёт неполный JSON, json_repair его починит
```

## Откат (если что-то пошло не так)

```bash
cd eatfit24-ai-proxy
git checkout v1.1.0  # Откат на предыдущую версию
docker compose down
docker compose up -d --build
```

## Мониторинг после деплоя

Первые 24 часа следить за:

1. **Ошибки 500** — должны почти исчезнуть
2. **Время ответа** — должно сократиться (меньше ретраев)
3. **Логи с "Unterminated string"** — не должно быть

```bash
# Отслеживание ошибок
docker compose logs -f | grep -i "error\|unterminated"

# Отслеживание успешных запросов
docker compose logs -f | grep "Successfully recognized"
```

## Ожидаемые метрики

**До (v1.1.0):**
- ~15-20% запросов падали с 500 ERROR
- Unterminated string errors

**После (v1.2.0):**
- <1% запросов с 500 ERROR
- json_repair автоматически чинит обрывы
- Быстрее фейлится при реальных проблемах

## Контакт

Если возникли проблемы при деплое, проверь:
1. Установился ли `json-repair` — `docker exec eatfit24-ai-proxy pip list | grep json-repair`
2. Логи контейнера — `docker compose logs --tail=100`
3. Переменные окружения — `.env` файл должен быть на месте

