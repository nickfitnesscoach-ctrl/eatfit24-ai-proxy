# Runbook — EatFit24 AI Proxy

Operational guide for managing the AI Proxy service.

---

## Quick Commands

### Build & Start

```bash
# Build and start in background
docker compose up -d --build

# View logs
docker compose logs -f

# Restart service
docker compose restart

# Stop service
docker compose down

# Rebuild from scratch
docker compose down && docker compose up -d --build
```

### Check Status

```bash
# Container status
docker compose ps

# Container resource usage
docker stats eatfit24-ai-proxy

# Check if running as non-root
docker exec eatfit24-ai-proxy id
# Expected: uid=1000(appuser) gid=1000(appuser)
```

---

## Health Check

### Local
```bash
curl http://localhost:8001/health
# Expected: {"status":"ok"}
```

### Remote (via Tailscale)
```bash
curl http://100.84.210.65:8001/health
```

### Docker Healthcheck Status
```bash
docker inspect --format='{{.State.Health.Status}}' eatfit24-ai-proxy
# Expected: healthy
```

---

## Test Requests

### Basic Test (Local)
```bash
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_PROXY_SECRET" \
  -F "image=@test_food_image.jpg" \
  -F "locale=ru"
```

### Test with Request ID
```bash
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_PROXY_SECRET" \
  -H "X-Request-ID: test-$(date +%s)" \
  -F "image=@test_food_image.jpg"
```

### Check Response Headers
```bash
curl -i -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_PROXY_SECRET" \
  -F "image=@test_food_image.jpg" 2>&1 | grep -i x-request-id
# Expected: X-Request-ID: <uuid>
```

---

## Troubleshooting

### 401 Unauthorized

**Cause:** Invalid or missing API key

**Check:**
1. Header name is exactly `X-API-Key` (case-sensitive)
2. Key matches `API_PROXY_SECRET` environment variable
3. No extra whitespace in the key

```bash
# Verify env var is set in container
docker exec eatfit24-ai-proxy printenv | grep API_PROXY_SECRET
```

### 429 Too Many Requests

**Cause:** OpenRouter rate limit exceeded

**What happens:**
- Service automatically retries 3 times with exponential backoff
- If still failing after retries, returns 500 to client

**Actions:**
1. Check OpenRouter dashboard for rate limits
2. Wait 1-5 minutes before retrying
3. Consider upgrading OpenRouter plan

**Log pattern:**
```json
{"msg": "OpenRouter returned 429, retrying in 1.0s (attempt 1/3)"}
```

### 500 AI Service Error

**Possible causes:**

1. **Timeout** — OpenRouter took too long
   - Current timeout: 30 seconds
   - Logs will show: `"Request to OpenRouter API timed out"`

2. **Invalid model** — Model doesn't exist or unavailable
   - Check `OPENROUTER_MODEL` is valid
   - Verify at https://openrouter.ai/models

3. **OpenRouter outage**
   - Check https://status.openrouter.ai

**Actions:**
1. Check logs for detailed error
2. Retry after 30 seconds
3. If persistent, check OpenRouter status

### 413 File Too Large

**Cause:** Image exceeds `MAX_IMAGE_SIZE_BYTES` (default 5MB)

**Solution:** Resize image before uploading

### Service Won't Start

**Cause:** Missing required environment variables

**Check:**
```bash
docker compose logs | head -50
```

**Expected error:**
```
pydantic_core._pydantic_core.ValidationError: ... Field required
```

**Fix:** Ensure `.env` file has all required variables:
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `API_PROXY_SECRET`

---

## Logs

### View Logs
```bash
# All logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Filter by request ID
docker compose logs | grep "abc12345"
```

### Log Format (JSON)
```json
{
  "ts": "2025-12-22T15:00:00",
  "level": "INFO",
  "logger": "app.main",
  "msg": "Request completed: POST /api/v1/ai/recognize-food -> 200",
  "request_id": "abc12345",
  "path": "/api/v1/ai/recognize-food",
  "method": "POST",
  "status": 200,
  "duration_ms": 2345.67,
  "client_ip": "100.84.210.65"
}
```

### Token Usage Logs
```json
{
  "msg": "OpenRouter token usage: prompt=1234, completion=567, total=1801"
}
```

---

## Resource Limits

Current limits (docker-compose.yml):
- Memory: 512MB
- CPU: 0.5 cores

To check usage:
```bash
docker stats eatfit24-ai-proxy --no-stream
```

---

## Deployment Checklist

Before deploying updates:

- [ ] `.env` has all required variables (no defaults)
- [ ] `API_PROXY_SECRET` is unique and strong (32+ chars)
- [ ] `OPENROUTER_MODEL` is a valid model ID
- [ ] Health check passes locally
- [ ] Test request works locally

After deployment:

- [ ] `docker compose ps` shows healthy
- [ ] `curl /health` returns 200
- [ ] Test request with real image works
- [ ] Logs show JSON format
- [ ] Response contains X-Request-ID
