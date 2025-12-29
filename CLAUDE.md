# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EatFit24 AI Proxy** is a stateless microservice that recognizes food from images and returns nutritional information (calories, protein, fat, carbohydrates). It acts as a proxy between the EatFit24 backend and OpenRouter AI models (GPT-4o-mini, Gemini 2.0 Flash, etc.).

**Key architectural principle:** This service is **stateless and does NOT implement user limits or billing**. All business quotas and pricing rules are handled by the backend. AI Proxy simply processes images and returns nutritional data.

## Development Commands

### Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment (required before starting)
cp .env.example .env
# Edit .env and set: OPENROUTER_API_KEY, OPENROUTER_MODEL, API_PROXY_SECRET

# Run with hot-reload
uvicorn app.main:app --reload --port 8001

# Health check
curl http://localhost:8001/health
```

### Testing

```bash
# Run integration tests
python tests/test_api.py

# Test specific scenarios
# - Scenario 1: With explicit weights in comment
# - Scenario 2: Without weights
# - Scenario 3: Empty comment

# Set environment variables for testing
export TEST_API_URL="http://localhost:8001/api/v1/ai/recognize-food"
export TEST_API_KEY="your-api-proxy-secret"
```

### Docker

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f

# Check status
docker compose ps
docker stats eatfit24-ai-proxy

# Restart
docker compose restart

# Rebuild from scratch
docker compose down && docker compose up -d --build
```

## Architecture

### Request Flow

1. **FastAPI endpoint** ([app/main.py](app/main.py)) receives multipart/form-data with image + optional comment
2. **Authentication** ([app/auth.py](app/auth.py)) validates X-API-Key header using timing-safe comparison
3. **OpenRouter client** ([app/openrouter_client.py](app/openrouter_client.py)) sends image + prompt to AI model
4. **Response parsing** validates and normalizes JSON from AI (handles field aliases: `carbs`→`carbohydrates`, `calories`→`kcal`)
5. **Schemas** ([app/schemas.py](app/schemas.py)) serialize response with both original and alias fields for frontend/backend compatibility

### Critical Components

#### Prompt Engineering (openrouter_client.py:54-226)

The prompt uses **weight prioritization logic**:
- If user comment contains explicit weights (e.g., "150 г"), the AI is instructed to **preserve those exact weights**
- AI uses the photo only to verify plausibility, not to override user-provided measurements
- This prevents the AI from "correcting" weights that users have already measured

#### Retry Logic

**HTTP-level retries** (openrouter_client.py:352-434):
- Retries 3 times for status codes: 429, 500, 502, 503, 504
- Exponential backoff: 1s → 2s → 4s (max 10s)
- Does NOT retry for: 400, 401, 403, 413, 422

**JSON validation retries** (openrouter_client.py:469-598):
- If AI returns invalid JSON, retries with stricter prompt (up to 3 attempts total)
- Fallback extraction attempts to find JSON object using regex if parsing fails

#### Field Normalization

LLM models may return different field names. Normalization happens in two places:

1. **Input normalization** (openrouter_client.py:229-253): Converts AI response fields (`carbs`→`carbohydrates`, `calories`→`kcal`)
2. **Output serialization** (schemas.py:28-41): Outputs BOTH formats for compatibility with frontend and backend

#### Logging

- **Structured JSON logs** with fields: `ts`, `level`, `msg`, `request_id`, `path`, `method`, `status`, `duration_ms`, `client_ip`
- **Request ID tracking** via ContextVar (main.py:14-15)
- Request IDs flow through: incoming header → context variable → logs → response header

### Configuration (app/config.py)

All settings loaded via pydantic-settings from `.env` file:

**Required (no defaults, service fails without these):**
- `OPENROUTER_API_KEY` - OpenRouter API key
- `OPENROUTER_MODEL` - Model ID (e.g., `openai/gpt-4o-mini`, `google/gemini-2.0-flash-001`)
- `API_PROXY_SECRET` - Authentication key for requests

**Optional:**
- `LOG_LEVEL` - Default: INFO
- `MAX_IMAGE_SIZE_BYTES` - Default: 5MB
- `OPENROUTER_BASE_URL` - Default: https://openrouter.ai/api/v1

### Security

- API key authentication using `secrets.compare_digest()` for timing-safety (auth.py:23)
- Container runs as non-root user (uid=1000)
- Resource limits: 512MB memory, 0.5 CPU cores
- Production deployment behind Tailscale VPN

## API Contract

**Single Source of Truth:** [app/schemas.py](app/schemas.py)

**Endpoint:** `POST /api/v1/ai/recognize-food`

**Request:**
- `image` (File): JPEG/PNG, max 5MB
- `user_comment` (string, optional): User description with weights
- `locale` (string, optional): "ru" or "en" (default: "ru")
- `X-API-Key` (header): Authentication key

**Response:**
```json
{
  "items": [
    {
      "name": "Куриная грудка гриль",
      "grams": 150.0,
      "amount_grams": 150.0,
      "kcal": 165.0,
      "calories": 165.0,
      "protein": 31.0,
      "fat": 3.6,
      "carbohydrates": 0.0,
      "carbs": 0.0
    }
  ],
  "total": {
    "kcal": 165.0,
    "calories": 165.0,
    "protein": 31.0,
    "fat": 3.6,
    "carbohydrates": 0.0,
    "carbs": 0.0
  },
  "model_notes": "Распознано на основе изображения"
}
```

**Note:** Both field name formats are returned for compatibility (internal: `kcal`/`carbohydrates`, aliases: `calories`/`carbs`/`amount_grams`).

## Common Modifications

### Changing the AI Model

Edit `.env` and update `OPENROUTER_MODEL`:
```bash
OPENROUTER_MODEL=google/gemini-2.0-flash-001
```

Restart the service. No code changes needed.

### Adjusting Retry Behavior

Edit [app/openrouter_client.py](app/openrouter_client.py):
- `RETRY_MAX_ATTEMPTS` (line 17) - Number of HTTP retries
- `RETRY_INITIAL_DELAY` (line 18) - Initial backoff delay
- `RETRYABLE_STATUS_CODES` (line 21) - Which status codes to retry
- `JSON_RETRY_MAX_ATTEMPTS` (line 25) - JSON validation retries
- `OPENROUTER_TIMEOUT` (line 28) - Request timeout in seconds

### Modifying Prompts

Prompts are in [app/openrouter_client.py](app/openrouter_client.py:54-226).

**Weight prioritization logic:**
- `has_explicit_grams()` (line 39) - Detects if comment has weights
- Prompt includes stronger instructions when weights are detected (lines 82-83, 158-159)

### Adding New Fields to Response

1. Update schema in [app/schemas.py](app/schemas.py) (add to `FoodItem` or `TotalNutrition`)
2. Update prompt in [app/openrouter_client.py](app/openrouter_client.py) to request new field
3. Update parsing logic in `parse_ai_response()` if needed (line 256)
4. Add field normalization in `normalize_item_fields()` if AI might return alternative names (line 229)

## Documentation

- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) - API specification (SSOT)
- [docs/API_DOCS.md](docs/API_DOCS.md) - Detailed API documentation
- [docs/ENV_CONTRACT.md](docs/ENV_CONTRACT.md) - Environment variables
- [docs/RUNBOOK.md](docs/RUNBOOK.md) - Operational procedures
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Version history

## Deployment

Production deployment is automated via GitHub Actions on push to `master`:
1. SSH to server via Tailscale
2. Pull latest code
3. Rebuild and restart containers
4. Verify health check

Manual deployment:
```bash
ssh user@server
cd eatfit24-ai-proxy
git pull
docker compose up -d --build
curl http://localhost:8001/health  # Verify
```
