# Roadmap: EatFit24 AI Proxy

## Phase 0 — Skeleton (ТЕКУЩАЯ)
- [x] Создать проект, venv, базовую структуру.
- [x] Реализовать FastAPI с /health.
- [x] Добавить схемы запроса/ответа и заглушку /api/v1/ai/recognize-food.

## Phase 1 — OpenRouter integration
- [ ] Добавить модуль `openrouter_client.py`.
- [ ] Вынести промпт и парсинг ответа модели.
- [ ] Подключить переменные окружения (`OPENROUTER_API_KEY` и т.д.).

## Phase 2 — Docker & Deploy
- [x] Написать Dockerfile.
- [x] Написать docker-compose.yml.
- [ ] Деплой на NL-сервер, проверка /health из РФ-сервера.

## Phase 3 — Security & Observability
- [ ] Ограничить доступ (Tailscale / firewall + API key).
- [ ] Добавить базовое логирование ошибок.
- [ ] Подготовить короткую API-доку для Django-бэкенда.

## Phase 4 — Optimization
- [ ] Тюнинг промпта под точность КБЖУ.
- [ ] Ограничения по таймаутам и размеру фото.
