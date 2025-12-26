# 🔧 Отчёт по аудиту AI-Proxy — EatFit24

**Дата:** 2025-12-26  
**Сервер:** 185.171.80.128 (NL, Timeweb)  
**Сервис:** eatfit24-ai-proxy (порт 8001)  
**Симптомы:** Таймауты >35s, Invalid JSON, английские имена продуктов

---

## 📋 Краткое резюме

| Проблема | Статус | Приоритет |
|----------|--------|-----------|
| Таймауты к OpenRouter | ⚠️ Требует диагностики | P0 |
| Invalid JSON ответы | 🔴 Найдено в коде | P0 |
| Английские имена вместо RU | 🔴 Нет RU-принуждения | P0 |
| Отсутствие JSON mode | 🟡 Улучшение | P1 |
| Модель может быть медленной | ⚠️ Требует проверки | P1 |

---

## ЧАСТЬ A — СЕРВЕРНАЯ ДИАГНОСТИКА (P0)

> **⚠️ ВАЖНО:** Для выполнения этих команд необходим SSH доступ к серверу.  
> Подключение: `ssh root@185.171.80.128` или через Tailscale `ssh root@100.84.210.65`

### A1) Проверка работоспособности сервиса

```bash
# Health check
curl -sS http://localhost:8001/health
# Ожидаемый результат: {"status":"ok"}

# Замер времени запроса (если есть тестовое изображение)
cd /opt/eatfit24-ai-proxy
time curl -w "\nTotal time: %{time_total}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\n" \
  -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $(grep API_PROXY_SECRET .env | cut -d= -f2)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "locale=ru"
```

**Ожидаемые результаты:**
- [ ] Статус 200 OK
- [ ] Время ответа < 35s
- [ ] Валидный JSON с полями `items`, `total`, `model_notes`

---

### A2) Статус контейнера и логи

```bash
# Статус контейнера
docker ps --filter name=eatfit24-ai-proxy --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Последние 300 строк логов
docker logs eatfit24-ai-proxy --tail 300

# Поиск ошибок за последние 2 часа
docker logs eatfit24-ai-proxy --since 2h 2>&1 | grep -Ei "timeout|openrouter|error|json|429|rate|trace|exception|failed"
```

**Что искать в логах:**
- `timeout` — таймауты к OpenRouter
- `429` — rate limiting
- `Invalid JSON` / `JSONDecodeError` — проблемы парсинга
- `carbohydrates Field required` — несоответствие схемы
- `duration_ms: >30000` — медленные запросы

---

### A3) Нагрузка на ресурсы

```bash
# Uptime и load average
uptime

# Top процессы
top -bn1 | head -40

# Память
free -h

# Диск
df -h

# Docker статистика
docker stats --no-stream
```

**Критерии проблем:**
| Метрика | Норма | Проблема |
|---------|-------|----------|
| Load average | < 2.0 | > 4.0 |
| Memory used | < 80% | > 90% или swap used |
| Disk used | < 80% | > 90% |
| Container CPU | < 50% | > 80% постоянно |
| Container MEM | < 400MB | > 450MB (лимит 512MB) |

---

### A4) Сетевая связь с OpenRouter

```bash
# С хоста
curl -w "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTLS: %{time_appconnect}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s -I https://openrouter.ai/api/v1

# Изнутри контейнера
docker exec eatfit24-ai-proxy curl -w "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTLS: %{time_appconnect}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s -I https://openrouter.ai/api/v1 2>/dev/null || echo "curl not available in container"

# DNS резолвинг
dig +short openrouter.ai
nslookup openrouter.ai
```

**Нормальные показатели:**
- DNS: < 50ms
- Connect: < 100ms  
- TLS: < 300ms
- Total: < 500ms

---

## ЧАСТЬ B — АНАЛИЗ КОРНЕВЫХ ПРИЧИН

### Выявленные проблемы в коде

#### 1. Таймаут AI-proxy = 30s (Строка 25 в `openrouter_client.py`)

```python
OPENROUTER_TIMEOUT = 30.0  # seconds (P1.3)
```

**Проблема:** Backend имеет `read_timeout=35s`, AI-proxy имеет timeout=30s. Если OpenRouter отвечает за 32-34s, AI-proxy успевает, но может оказаться впритык.

**Риск:** При 3 retry с backoff (1s + 2s + 4s = 7s задержки) + 30s × 3 = 97s максимум — может превысить backend timeout.

---

#### 2. Нет JSON mode в запросе к OpenRouter

**Текущий код (строка 413-431 в `openrouter_client.py`):**
```python
payload = {
    "model": settings.openrouter_model,
    "max_tokens": OPENROUTER_MAX_TOKENS,
    "messages": [...]
}
# ❌ Нет response_format: {"type": "json_object"}
# ❌ Нет temperature: 0
```

**Следствие:** Модель может вернуть невалидный JSON (markdown, комментарии, обрезанный ответ).

---

#### 3. Недостаточная валидация JSON ответа

**Текущий код (строки 235-286 в `openrouter_client.py`):**
```python
def parse_ai_response(response_text: str) -> tuple[List[FoodItem], Optional[str]]:
    # Есть: удаление markdown ```json...```
    # Есть: normalize_item_fields (carbs → carbohydrates)
    # ❌ Нет: try repair если JSON сломан
    # ❌ Нет: логирование raw response при ошибке
```

---

#### 4. Промпт не принуждает к RU именам

**Текущий промпт (строки 82-136):**
- ✅ Промпт на русском
- ❌ Нет явного указания: "ВСЕ названия продуктов ТОЛЬКО на русском"
- ❌ Нет примера желаемого вывода с RU именами

---

### Наиболее вероятные причины по bucket'ам

| # | Причина | Вероятность | Доказательства |
|---|---------|-------------|----------------|
| 2 | OpenRouter медленный/нестабильный | **ВЫСОКАЯ** | Timeout 30s, retry логика |
| 4 | Парсинг JSON | **ВЫСОКАЯ** | Предыдущий аудит показал ошибки `carbs` |
| 3 | Модель слишком медленная | **СРЕДНЯЯ** | Нужно проверить OPENROUTER_MODEL |
| 1 | Сервер перегружен | НИЗКАЯ | Предыдущий аудит: 10% RAM usage |
| 5 | Проблема конкурентности | НИЗКАЯ | Нет глобального state |

---

## ЧАСТЬ C — ПЛАН ИСПРАВЛЕНИЙ (P0/P1)

### C1) Стратегия таймаутов (P0)

#### Изменения в AI-proxy (`openrouter_client.py`):

```python
# Строка 25 — изменить:
OPENROUTER_TIMEOUT = 45.0  # seconds (было 30.0)

# Добавить после строки 25:
OPENROUTER_CONNECT_TIMEOUT = 10.0  # seconds
```

```python
# Строка 434 — изменить создание клиента:
async with httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=OPENROUTER_CONNECT_TIMEOUT,
        read=OPENROUTER_TIMEOUT,
        write=OPENROUTER_TIMEOUT,
        pool=OPENROUTER_TIMEOUT
    )
) as client:
```

#### Рекомендация для backend:
- Временно увеличить `read_timeout_s` до 60s
- После стабилизации вернуть на 45s

---

### C2) Hardening для Invalid JSON (P0)

#### Добавить response_format в payload (`openrouter_client.py`, после строки 430):

```python
payload = {
    "model": settings.openrouter_model,
    "max_tokens": OPENROUTER_MAX_TOKENS,
    "temperature": 0,  # ← ДОБАВИТЬ: детерминированный вывод
    "response_format": {"type": "json_object"},  # ← ДОБАВИТЬ: JSON mode
    "messages": [...]
}
```

> **⚠️ ВАЖНО:** Не все модели поддерживают `response_format`. Проверить для текущей модели!

#### Добавить JSON repair логику (`openrouter_client.py`, в `parse_ai_response`):

```python
def extract_first_json_object(text: str) -> Optional[str]:
    """Извлечь первый валидный JSON объект из текста."""
    import re
    # Попытка найти JSON между { и }
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            json.loads(match.group())
            return match.group()
        except json.JSONDecodeError:
            pass
    return None

def parse_ai_response(response_text: str) -> tuple[List[FoodItem], Optional[str]]:
    try:
        text = response_text.strip()
        
        # Удаление markdown
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Попытка парсинга
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Попытка извлечь JSON объект
            extracted = extract_first_json_object(response_text)
            if extracted:
                logger.warning(f"Extracted JSON from malformed response")
                data = json.loads(extracted)
            else:
                # Логируем первые 200 символов для отладки (без секретов)
                logger.error(
                    f"Failed to parse AI response, raw (first 200 chars): "
                    f"{response_text[:200]}"
                )
                raise OpenRouterError(
                    code="AI_INVALID_JSON",
                    message="Could not parse AI response as valid JSON"
                )
        
        # ... остальной код
```

---

### C3) Русские названия продуктов (P0)

#### Опция A (предпочтительная): Усиление промпта

**Изменения в `build_food_recognition_prompt` (`openrouter_client.py`, строка 82):**

```python
# Добавить в начало промпта (после строки 82):
base_prompt = f"""Ты — эксперт по питанию и взвешиванию порций. У тебя есть:
1) ФОТО блюда.
2) КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ с описанием и весами продуктов.

⚠️ **КРИТИЧЕСКИ ВАЖНО — ЯЗЫК ОТВЕТА:**
- ВСЕ названия продуктов ДОЛЖНЫ быть на РУССКОМ ЯЗЫКЕ.
- НЕ ИСПОЛЬЗУЙ английские названия (chicken → курица, rice → рис).
- Если не знаешь русское название — используй транслитерацию.

Сначала ВНИМАТЕЛЬНО ПРОЧИТАЙ комментарий, потом смотри на фото.
{comment_section}{weight_instruction}
...
```

#### Добавить пример в формат ответа:

```python
# В секции ФОРМАТ ОТВЕТА, изменить пример:
ФОРМАТ ОТВЕТА — СТРОГО JSON без лишнего текста:

{{
  "items": [
    {{
      "name": "Куриная грудка гриль",  // ← ПРИМЕР НА РУССКОМ
      "grams": 150.0,
      "kcal": 247.5,
      "protein": 46.5,
      "fat": 5.4,
      "carbohydrates": 0.0
    }},
    {{
      "name": "Отварной рис",  // ← ПРИМЕР НА РУССКОМ
      "grams": 200.0,
      "kcal": 260.0,
      "protein": 5.4,
      "fat": 0.6,
      "carbohydrates": 56.8
    }}
  ],
  ...
}}
```

---

### C4) Оптимизация модели (P1)

#### Проверить текущую модель:

```bash
# На сервере:
grep OPENROUTER_MODEL /opt/eatfit24-ai-proxy/.env
```

#### Рекомендуемые модели по скорости/качеству:

| Модель | Latency | Качество | Cost |
|--------|---------|----------|------|
| `google/gemini-2.0-flash-001` | ~5-10s | Отличное | Низкая |
| `openai/gpt-4o-mini` | ~10-15s | Хорошее | Средняя |
| `anthropic/claude-3-haiku` | ~8-12s | Хорошее | Низкая |
| `openai/gpt-4o` | ~15-25s | Отличное | Высокая |

#### Добавить fallback модель (опционально):

```python
# В config.py:
openrouter_fallback_model: Optional[str] = Field(
    default=None,
    description="Fallback model if primary times out"
)

# В openrouter_client.py:
# После timeout на primary модели — retry с fallback
```

---

## ЧАСТЬ D — OBSERVABILITY (P0)

### Текущее состояние (✅ уже реализовано):

```python
# В main.py:
- request_id генерируется/принимается из X-Request-ID
- Логируется: path, method, status, duration_ms, client_ip
- JSON формат логов

# В openrouter_client.py:
- Логируется token usage
- Логируются ошибки OpenRouter
```

### Рекомендуемые улучшения:

#### Добавить метрики времени к OpenRouter (`openrouter_client.py`):

```python
async def recognize_food_with_bytes(...):
    start_time = time.time()
    
    # ... вызов OpenRouter ...
    
    openrouter_time_ms = (time.time() - start_time) * 1000
    
    logger.info(
        f"OpenRouter call completed",
        extra={
            "time_to_openrouter_ms": openrouter_time_ms,
            "model": settings.openrouter_model,
            "items_count": len(items)
        }
    )
```

#### Логировать raw response при ошибке парсинга:

```python
except json.JSONDecodeError as e:
    # Маскируем потенциально чувствительные данные
    safe_preview = response_text[:200].replace('\n', ' ')
    logger.error(
        f"JSON parse failed: {e}",
        extra={
            "raw_response_preview": safe_preview,
            "response_length": len(response_text)
        }
    )
```

---

## 📋 Чеклист верификации

### После применения фиксов:

```bash
# 1. Пересобрать контейнер
cd /opt/eatfit24-ai-proxy
git pull origin master
docker compose down && docker compose up -d --build

# 2. Проверить health
curl http://localhost:8001/health

# 3. Тестовый запрос
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $(grep API_PROXY_SECRET .env | cut -d= -f2)" \
  -H "X-Request-ID: test-$(date +%s)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "locale=ru" \
  | jq .

# 4. Проверить имена на русском
# Ожидаемо: "name": "Куриная грудка", НЕ "name": "Chicken breast"

# 5. Проверить логи
docker logs eatfit24-ai-proxy --tail 50 | jq .

# 6. Замерить время
time curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $(grep API_PROXY_SECRET .env | cut -d= -f2)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -o /dev/null -s

# Ожидаемо: < 35 секунд
```

---

## 🔙 План отката

Если фиксы вызвали проблемы:

```bash
cd /opt/eatfit24-ai-proxy

# Откат на предыдущий коммит
git log --oneline -5  # найти предыдущий коммит
git checkout <previous-commit-hash>

# Пересобрать
docker compose down && docker compose up -d --build

# Проверить
curl http://localhost:8001/health
```

---

## 📝 Smoke Test — финальные команды

```bash
# ====== ПОЛНЫЙ SMOKE TEST ======

# 1. Health check
echo "=== Health Check ==="
curl -s http://localhost:8001/health | jq .

# 2. Recognize with timing
echo -e "\n=== Recognize Food (с замером времени) ==="
time curl -s -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $(grep API_PROXY_SECRET .env | cut -d= -f2)" \
  -H "X-Request-ID: smoke-test-$(date +%s)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "user_comment=тест распознавания" \
  -F "locale=ru" \
  | jq .

# 3. Проверка X-Request-ID в ответе
echo -e "\n=== Response Headers ==="
curl -s -I -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $(grep API_PROXY_SECRET .env | cut -d= -f2)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  2>&1 | grep -i x-request-id

# 4. Недействительный API ключ (должен вернуть 401)
echo -e "\n=== Auth Test (expect 401) ==="
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: invalid-key" \
  -F "image=@tests/assets/test_food_image.jpg"
echo " (expected: 401)"

# 5. Проверка логов
echo -e "\n=== Last 10 Log Lines ==="
docker logs eatfit24-ai-proxy --tail 10 2>&1 | head -10
```

---

## 📊 Итоговая сводка

### Критические исправления (P0):

1. **Таймауты** — увеличить `OPENROUTER_TIMEOUT` до 45s
2. **JSON mode** — добавить `response_format: {"type": "json_object"}` и `temperature: 0`
3. **JSON repair** — добавить fallback извлечение JSON
4. **RU имена** — усилить промпт с явным требованием русского языка

### Улучшения (P1):

1. **Fallback модель** — настроить вторую модель при timeout
2. **Мониторинг** — добавить `time_to_openrouter_ms` в логи
3. **LOG_LEVEL** — сменить на INFO в production

---

**Отчёт подготовлен:** 2025-12-26  
**Версия:** 1.0  
**Статус:** Готов к выполнению диагностики на сервере
