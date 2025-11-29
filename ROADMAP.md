# Roadmap: EatFit24 AI Proxy

## Phase 0 — Skeleton
- [x] Создать проект, venv, базовую структуру.
- [x] Реализовать FastAPI с /health.
- [x] Добавить схемы запроса/ответа и заглушку /api/v1/ai/recognize-food.

## Phase 1 — OpenRouter integration
- [x] Добавить модуль `openrouter_client.py`.
- [x] Вынести промпт и парсинг ответа модели.
- [x] Подключить переменные окружения (`OPENROUTER_API_KEY` и т.д.).
- [x] Создать модуль `config.py` для управления настройками.
- [x] Интегрировать OpenRouter в эндпоинт `/api/v1/ai/recognize-food`.

## Phase 2 — Docker & Deploy
- [x] Написать Dockerfile.
- [x] Написать docker-compose.yml.
- [x] Добавить .dockerignore для оптимизации сборки.
- [x] Добавить healthcheck в docker-compose.yml.
- [x] Протестировать сборку и запуск в Docker.
- [x] Деплой на NL-сервер, проверка /health из РФ-сервера.

## Phase 3 — Security & Observability (ТЕКУЩАЯ)
- [ ] Ограничить доступ (Tailscale / firewall + API key).
- [ ] Добавить базовое логирование ошибок.
- [ ] Подготовить короткую API-доку для Django-бэкенда.

## Phase 4 — Optimization
- [ ] Тюнинг промпта под точность КБЖУ.
- [ ] Ограничения по таймаутам и размеру фото.
