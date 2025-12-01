# Migration to Multipart/Form-Data

## Summary

Successfully migrated the AI proxy from JSON with `image_url` to `multipart/form-data` with file uploads.

### What Changed

1. **Endpoint accepts multipart/form-data instead of JSON**
   - `image`: UploadFile (required) - JPEG/PNG file
   - `user_comment`: Form field (optional) - string
   - `locale`: Form field (optional, default: "ru") - string

2. **File validation added**
   - Maximum file size: 5 MB (configurable via `MAX_IMAGE_SIZE_BYTES`)
   - Allowed formats: JPEG, PNG only
   - Empty files rejected with 400 error
   - Oversized files rejected with 413 error

3. **Response format unchanged**
   - Same JSON structure as before
   - Backward compatible for consumers

## Files Modified

### 1. [app/schemas.py](app/schemas.py)
- **Removed**: `RecognizeFoodRequest` class with `HttpUrl` field
- **Kept**: All response schemas (FoodItem, TotalNutrition, RecognizeFoodResponse)

### 2. [app/config.py](app/config.py)
- **Added**: `max_image_size_bytes` setting (default: 5 MB)

### 3. [app/main.py](app/main.py)
- **Changed**: Endpoint signature from JSON body to multipart form
  - Before: `payload: RecognizeFoodRequest`
  - After: `image: UploadFile`, `user_comment: Optional[str] = Form(None)`, `locale: str = Form("ru")`
- **Added**: File validation logic (type, size, empty check)
- **Added**: `ALLOWED_CONTENT_TYPES` constant
- **Changed**: Logging to include file metadata (size, type) instead of URL

### 4. [app/openrouter_client.py](app/openrouter_client.py)
- **Added**: `recognize_food_with_bytes()` function
  - Accepts: `image_bytes`, `filename`, `content_type`, `user_comment`, `locale`
  - Converts bytes to base64 data URL internally
  - Sends to OpenRouter API
- **Updated**: `build_food_recognition_prompt()` - removed `image_url` parameter

### 5. [API_DOCS.md](API_DOCS.md)
- **Updated**: Request format examples to show multipart/form-data
- **Added**: cURL example with `-F` flags
- **Updated**: Error responses to include 400 (bad file type), 413 (file too large)
- **Updated**: Python integration examples for both standalone and Django
- **Added**: Notes about file size limits and supported formats

### 6. [README.md](README.md)
- **Updated**: Description to mention "файл изображения" instead of "по URL"
- **Updated**: Example request to use multipart/form-data
- **Added**: Environment variable documentation for `MAX_IMAGE_SIZE_BYTES`

## Breaking Changes

- **JSON requests with `image_url` are NO LONGER supported**
- Clients must send `multipart/form-data` with file uploads
- Django backend integration needs to be updated accordingly

## Deployment Instructions

### On NL Server (100.84.210.65)

```bash
# SSH into the server
ssh user@100.84.210.65

# Navigate to project directory
cd /opt/eatfit24-ai-proxy

# Pull latest changes
git pull origin master

# Rebuild and restart Docker container
docker compose down
docker compose up -d --build

# Verify the service is running
docker compose ps
docker logs eatfit24-ai-proxy --tail 50

# Test the endpoint
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "image=@/path/to/test-image.jpg" \
  -F "locale=ru"
```

### Environment Variables

Ensure `.env` file has:
```
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-5-image-mini
API_PROXY_SECRET=your_secret_here
MAX_IMAGE_SIZE_BYTES=5242880  # Optional, default: 5 MB
```

## Testing Checklist

- [ ] Small JPEG file (<500 KB) → 200 OK
- [ ] PNG file (<2 MB) → 200 OK
- [ ] File >5 MB → 413 Payload Too Large
- [ ] Unsupported format (GIF, PDF) → 400 Bad Request
- [ ] Empty file → 400 Bad Request
- [ ] Request without image → 422 Validation Error
- [ ] Request without user_comment → 200 OK (optional field works)
- [ ] Request with user_comment → 200 OK
- [ ] Invalid API key → 401 Unauthorized
- [ ] Valid request with locale=ru → 200 OK (Russian response)
- [ ] Valid request with locale=en → 200 OK (English response)

## Integration Updates Required

### Django Backend

Update the Django view that calls this API:

```python
# OLD CODE (no longer works)
response = requests.post(
    f"{AI_PROXY_URL}/api/v1/ai/recognize-food",
    json={"image_url": image_url, "locale": "ru"},
    headers={"X-API-Key": API_KEY}
)

# NEW CODE
with open(image_path, 'rb') as f:
    response = requests.post(
        f"{AI_PROXY_URL}/api/v1/ai/recognize-food",
        files={"image": f},
        data={"locale": "ru", "user_comment": comment},
        headers={"X-API-Key": API_KEY}
    )
```

Or if receiving from Django request:

```python
image_file = request.FILES['image']
response = requests.post(
    f"{AI_PROXY_URL}/api/v1/ai/recognize-food",
    files={"image": (image_file.name, image_file.read(), image_file.content_type)},
    data={"locale": "ru"},
    headers={"X-API-Key": API_KEY}
)
```

## Security & Privacy

- Image file content is NOT logged (only metadata: size, type, filename)
- Files are read into memory and immediately discarded after processing
- No persistent storage of uploaded files
- File size limited to prevent DoS attacks
- Only JPEG/PNG allowed to prevent malicious file uploads

## Performance Considerations

- Base64 encoding increases data size by ~33%
- 5 MB file → ~6.7 MB base64 string in memory
- Memory usage is temporary (released after request)
- OpenRouter API handles base64 data URLs efficiently

## Rollback Plan

If issues occur, rollback steps:

```bash
cd /opt/eatfit24-ai-proxy
git log --oneline -5  # Find commit hash before migration
git checkout <previous_commit_hash>
docker compose up -d --build
```

Then notify Django team to revert their integration changes.

---

**Migration Date**: 2025-11-29
**Author**: Claude Code
**Status**: ✅ Ready for deployment
