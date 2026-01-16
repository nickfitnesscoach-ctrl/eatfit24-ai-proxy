# Anti-Hallucination Gate

Предотвращает «галлюцинации» AI на изображениях без еды или с плохо различимой едой.

## Как работает

```
Image → [Gate Check] → Food? → [Main Recognition] → Result
                    ↓ No food
                UNSUPPORTED_CONTENT
```

1. **Gate Check** — быстрая проверка: есть ли еда на фото?
2. **Threshold** — если `confidence < 0.60` — отказ
3. **Main Recognition** — полное распознавание блюд
4. **Post-Validation** — проверка на пустой результат

## Коды ошибок

| Error Code | HTTP | Описание |
|------------|------|----------|
| `UNSUPPORTED_CONTENT` | 400 | На фото нет еды |
| `EMPTY_RESULT` | 400 | Еда есть, но распознать не удалось |
| `INVALID_IMAGE` | 400 | Файл не читается |
| `UNSUPPORTED_IMAGE_FORMAT` | 400 | Не JPEG/PNG |
| `IMAGE_TOO_LARGE` | 413 | Больше 5 МБ |
| `UPSTREAM_ERROR` | 502 | Ошибка AI провайдера |
| `UPSTREAM_TIMEOUT` | 504 | Таймаут AI провайдера |
| `RATE_LIMIT` | 429 | Превышен лимит запросов |

## Пороги

```env
FOOD_GATE_THRESHOLD=0.60      # Минимум confidence для прохода gate
RECOGNITION_THRESHOLD=0.65    # (на будущее)
```

## Trace ID

- Входящий header: `X-Trace-Id` (или `X-Request-ID`)
- Генерируется если не передан: `uuid4().hex` (32 символа)
- Возвращается в body `trace_id` + header `X-Trace-Id`
- Логируется во всех structured logs

## Формат ответов

### Success

```json
{
  "status": "success",
  "is_food": true,
  "confidence": 0.82,
  "gate_reason": "food visible",
  "trace_id": "a1b2c3d4e5f6789012345678",
  "result": {
    "items": [...],
    "total": {...},
    "model_notes": "..."
  }
}
```

### Error

```json
{
  "status": "error",
  "error_code": "UNSUPPORTED_CONTENT",
  "user_title": "Похоже, на фото не еда",
  "user_message": "Сфотографируйте блюдо крупнее при хорошем освещении.",
  "user_actions": ["retake"],
  "allow_retry": false,
  "trace_id": "a1b2c3d4e5f6789012345678",
  "error": "UNSUPPORTED_CONTENT",
  "error_message": "Сфотографируйте блюдо крупнее при хорошем освещении."
}
```

## Совместимость

Флаг `AI_PROXY_ERROR_HTTP200_COMPAT=true` — ошибки возвращаются с HTTP 200 (для legacy backend).

## Логи

Structured JSON logs с полями:
- `trace_id`
- `gate.is_food`, `gate.confidence`
- `final_status` (success/error)
- `error_code`

## Тесты

```bash
# Unit tests (mocked, fast)
pytest tests/test_food_gate.py -v

# Integration tests (requires running server)
python tests/integration_test.py
```
