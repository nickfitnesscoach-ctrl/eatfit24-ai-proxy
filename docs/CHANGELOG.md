# Changelog

All notable changes to EatFit24 AI Proxy.

---

## [1.1.0] - 2025-12-22

### Security (P0)

- **BREAKING:** `API_PROXY_SECRET` is now required — no default value
- **BREAKING:** `OPENROUTER_MODEL` is now required — no default value
- Added timing-safe comparison for API key (prevents timing attacks)
- Removed hardcoded secrets from `test_api.py`
- Deleted garbage file `nul` from repository

### Reliability (P1)

- Added retry with exponential backoff for OpenRouter calls
  - 3 attempts for 429/5xx/timeout errors
  - Backoff: 1s → 2s → 4s (max 10s)
  - No retry for 4xx client errors
- Reduced OpenRouter timeout from 60s to 30s
- Added `max_tokens: 2000` to limit response size and cost
- Added `detail: "low"` for images to reduce token usage

### Observability (P1)

- Added Request ID middleware
  - Accepts `X-Request-ID` from incoming requests
  - Generates UUID if not provided
  - Returns `X-Request-ID` in response headers
  - Includes request_id in all log entries
- Implemented structured JSON logging
  - Fields: ts, level, msg, request_id, path, method, status, duration_ms, client_ip
- Added token usage logging (prompt/completion/total tokens)

### Hardening (P2)

- Dockerfile now runs as non-root user (`appuser`)
- Added resource limits in docker-compose.yml (512MB, 0.5 CPU)

### Documentation

- Created `docs/API_CONTRACT.md` — SSOT for API schemas
- Created `docs/ENV_CONTRACT.md` — Environment variables reference
- Created `docs/RUNBOOK.md` — Operational guide
- Updated `docs/API_DOCS.md` — Fixed field names to match actual schemas
- Updated `README.md` — Added troubleshooting, updated quick start

---

## [1.0.0] - 2025-12-21

### Initial Release

- Food recognition via OpenRouter vision models
- Multipart/form-data API for image upload
- Weight prioritization from user comments
- Russian and English locale support
- Docker deployment ready
- Tailscale VPN + API key authentication
