import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from app.schemas import RecognizeFoodResponse
from app.openrouter_client import recognize_food_with_bytes, OpenRouterError
from app.auth import verify_api_key
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="EatFit24 AI Proxy")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing information"""
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url.path} from {request.client.host}")

    # Process request
    response = await call_next(request)

    # Log response with duration
    duration = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Duration: {duration:.3f}s"
    )

    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}


@app.post("/api/v1/ai/recognize-food", response_model=RecognizeFoodResponse)
async def recognize_food(
    image: UploadFile = File(..., description="Food image file (JPEG/PNG)"),
    user_comment: Optional[str] = Form(None, description="Optional comment about the food"),
    locale: str = Form("ru", description="Language locale (ru/en)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Recognize food items in an image and return nutritional information

    Args:
        image: Uploaded image file (JPEG or PNG format)
        user_comment: Optional comment describing the food
        locale: Language locale for response (default: "ru")
        api_key: API key for authentication (provided via X-API-Key header)

    Returns:
        RecognizeFoodResponse with food items, totals, and optional model notes

    Raises:
        HTTPException: 401 for invalid API key, 400 for bad requests, 413 for file too large, 500 for server/API errors
    """
    try:
        # Validate content type
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Unsupported file type: {image.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {image.content_type}. Only JPEG/PNG are allowed."
            )

        # Read file content
        content = await image.read()

        # Validate file size
        file_size = len(content)
        if file_size == 0:
            logger.warning("Empty file uploaded")
            raise HTTPException(status_code=400, detail="Empty file.")

        if file_size > settings.max_image_size_bytes:
            logger.warning(f"File too large: {file_size} bytes (max: {settings.max_image_size_bytes})")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max allowed size is {settings.max_image_size_bytes} bytes ({settings.max_image_size_bytes // (1024*1024)} MB)."
            )

        logger.info(
            f"Processing food recognition request - "
            f"file: {image.filename}, size: {file_size} bytes, type: {image.content_type}, locale: {locale}"
        )

        items, total, model_notes = await recognize_food_with_bytes(
            image_bytes=content,
            filename=image.filename or "image.jpg",
            content_type=image.content_type or "image/jpeg",
            user_comment=user_comment,
            locale=locale
        )

        logger.info(f"Successfully recognized {len(items)} food items")

        return RecognizeFoodResponse(
            items=items,
            total=total,
            model_notes=model_notes
        )

    except OpenRouterError as e:
        logger.error(f"OpenRouter error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
