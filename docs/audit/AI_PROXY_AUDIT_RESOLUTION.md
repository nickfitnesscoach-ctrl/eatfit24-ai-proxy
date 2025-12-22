# AI Proxy Audit Resolution

**Date:** 2025-12-22  
**Status:** ✅ COMPLETED

This document summarizes all fixes implemented based on the [AI_PROXY_AUDIT.md](AI_PROXY_AUDIT.md).

---

## P0 — Critical Fixes (DONE)

| Issue | Status | File | What Changed |
|-------|--------|------|--------------|
| P0.1 Add max_tokens | ✅ Fixed | `app/openrouter_client.py` | Added `max_tokens: 2000` to payload |
| P0.2 Remove default for API_PROXY_SECRET | ✅ Fixed | `app/config.py` | Made field required with `Field(...)` |
| P0.3 Timing-safe API key compare | ✅ Fixed | `app/auth.py` | Using `secrets.compare_digest()` |
| P0.4 Remove garbage file `nul` | ✅ Fixed | Root directory | File deleted |
| P0.4 Remove hardcoded secret from tests | ✅ Fixed | `test_api.py` | Reads from `TEST_API_KEY` or `API_PROXY_SECRET` env |

### Verification
- Service fails to start without required env vars (Pydantic ValidationError)
- API key comparison is timing-safe
- No secrets in git

---

## P1 — Reliability + Observability (DONE)

| Issue | Status | File | What Changed |
|-------|--------|------|--------------|
| P1.1 Request ID middleware | ✅ Fixed | `app/main.py` | Middleware generates/uses X-Request-ID, adds to logs and response |
| P1.2 Retry + exponential backoff | ✅ Fixed | `app/openrouter_client.py` | 3 attempts, 1s→2s→4s backoff, retries 429/5xx/timeout |
| P1.3 Reduce timeout to 30s | ✅ Fixed | `app/openrouter_client.py` | `OPENROUTER_TIMEOUT = 30.0` |
| P1.4 Explicit image detail | ✅ Fixed | `app/openrouter_client.py` | Added `detail: "low"` to image payload |
| P1.5 Sync docs with real schemas | ✅ Fixed | `docs/API_DOCS.md` | Changed to `name`, `grams`, `kcal`, `protein`, `fat`, `carbs` |
| P1.6 Fix default model | ✅ Fixed | `app/config.py` | Made `OPENROUTER_MODEL` required (no potentially invalid default) |

### Verification
- Response headers contain `X-Request-ID`
- Logs contain `request_id` field
- Retry visible in logs on 429/5xx
- `docs/API_DOCS.md` matches `app/schemas.py`

---

## P2 — Hardening (DONE)

| Issue | Status | File | What Changed |
|-------|--------|------|--------------|
| P2.1 Non-root user in Docker | ✅ Fixed | `Dockerfile` | Created `appuser`, runs with `USER appuser` |
| P2.2 Resource limits in compose | ✅ Fixed | `docker-compose.yml` | Added `mem_limit: 512m`, `cpus: 0.5` |
| P2.3 Structured JSON logs | ✅ Fixed | `app/main.py` | `JSONFormatter` outputs ts, level, msg, request_id, path, status, duration_ms |
| P2.4 Log token usage | ✅ Fixed | `app/openrouter_client.py` | Logs prompt/completion/total tokens from OpenRouter response |
| P2.5 Rate limiting | ⏭️ Skipped | N/A | Not needed (Tailscale VPN only access) |

### Verification
- `docker exec <container> id` shows uid≠0
- Logs parse as valid JSON
- Token usage appears in logs on successful requests

---

## Documentation (DONE)

| Document | Status | Description |
|----------|--------|-------------|
| `README.md` | ✅ Updated | Full rewrite with troubleshooting, env requirements |
| `docs/API_CONTRACT.md` | ✅ Created | SSOT for API schemas, error table |
| `docs/ENV_CONTRACT.md` | ✅ Created | All env vars with required/optional |
| `docs/RUNBOOK.md` | ✅ Created | Operational commands, troubleshooting, deployment checklist |
| `docs/CHANGELOG.md` | ✅ Created | P0/P1/P2 changes documented |
| `docs/API_DOCS.md` | ✅ Updated | Fixed field names to match schemas.py |

---

## Files Changed

### Modified
- `app/config.py` — Required secrets, no defaults
- `app/auth.py` — Timing-safe compare
- `app/openrouter_client.py` — Retry, timeout, max_tokens, detail, token logging
- `app/main.py` — Request ID middleware, JSON logging
- `test_api.py` — Read secrets from env
- `Dockerfile` — Non-root user
- `docker-compose.yml` — Resource limits
- `docs/API_DOCS.md` — Correct schemas
- `README.md` — Full rewrite

### Created
- `docs/API_CONTRACT.md`
- `docs/ENV_CONTRACT.md`
- `docs/RUNBOOK.md`
- `docs/CHANGELOG.md`
- `AI_PROXY_AUDIT_RESOLUTION.md` (this file)

### Deleted
- `nul` (garbage file)

---

## Definition of Done ✅

- [x] Service doesn't start without `OPENROUTER_API_KEY` and `API_PROXY_SECRET`
- [x] `max_tokens` and `detail` are set in OpenRouter requests
- [x] Retry/backoff works for 429/5xx/timeout (3 attempts)
- [x] Request ID in responses and logs
- [x] Documentation matches real JSON and env
- [x] No hardcoded secrets in git
- [x] No garbage files in repository
