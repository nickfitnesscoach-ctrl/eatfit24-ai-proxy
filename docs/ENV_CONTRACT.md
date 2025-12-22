# Environment Variables Contract — EatFit24 AI Proxy

This document defines all environment variables for the AI Proxy service.

---

## Required Variables

> ⚠️ **Service will not start without these variables.**

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM access | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | OpenRouter model ID (must be valid vision model) | `openai/gpt-4o-mini` |
| `API_PROXY_SECRET` | Authentication key for incoming requests | `my-super-long-random-secret-32chars` |

### Valid Model Examples

- `openai/gpt-4o-mini` — Cost-effective, good quality
- `openai/gpt-4o` — Higher quality, more expensive
- `google/gemini-2.0-flash-001` — Fast, good for prototyping
- `anthropic/claude-3.5-sonnet` — High quality responses

> 📌 Check [OpenRouter Models](https://openrouter.ai/models) for current availability.

---

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `APP_NAME` | `EatFit24 AI Proxy` | Application name (for logs) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MAX_IMAGE_SIZE_BYTES` | `5242880` (5 MB) | Maximum allowed image file size |

---

## Example Configurations

### Development (.env)

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-your-dev-key
OPENROUTER_MODEL=google/gemini-2.0-flash-001
API_PROXY_SECRET=dev-secret-change-in-prod

# Optional
LOG_LEVEL=DEBUG
```

### Production (.env)

```bash
# Required - NO DEFAULTS IN PRODUCTION
OPENROUTER_API_KEY=sk-or-v1-your-prod-key
OPENROUTER_MODEL=openai/gpt-4o-mini
API_PROXY_SECRET=production-random-string-minimum-32-characters

# Optional
LOG_LEVEL=INFO
MAX_IMAGE_SIZE_BYTES=5242880
```

---

## Security Rules

> 🚨 **CRITICAL: Never commit secrets to Git!**

1. **Never use default values in production**
   - `API_PROXY_SECRET` has NO default — service won't start without it
   
2. **Generate strong secrets**
   ```bash
   # Generate a random secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **File permissions**
   ```bash
   chmod 600 .env  # Owner read/write only
   ```

4. **gitignore**
   - `.env` is already in `.gitignore`
   - Use `.env.example` for documentation (no real secrets)

---

## Validation Errors

If required variables are missing, service will fail with Pydantic ValidationError:

```
pydantic_core._pydantic_core.ValidationError: 3 validation errors for Settings
openrouter_api_key
  Field required [type=missing, input_value={}, input_type=dict]
openrouter_model
  Field required [type=missing, input_value={}, input_type=dict]
api_proxy_secret
  Field required [type=missing, input_value={}, input_type=dict]
```

---

## Quick Reference

```bash
# Check current env (without exposing secrets)
docker exec eatfit24-ai-proxy env | grep -E "^(OPENROUTER_MODEL|LOG_LEVEL|APP_NAME)"
```
