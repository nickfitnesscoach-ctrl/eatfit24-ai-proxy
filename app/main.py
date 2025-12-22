import logging
import time
import json
import uuid
import sys
from contextvars import ContextVar
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile, Form
from app.schemas import RecognizeFoodResponse
from app.openrouter_client import recognize_food_with_bytes, OpenRouterError
from app.auth import verify_api_key
from app.config import settings

# Context variable for request ID (P1.1)
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging (P2.3).

    Outputs logs as JSON with fields: ts, level, msg, request_id, logger, extra
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Add request_id if available
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id

        # Add extra fields if present
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """Configure JSON structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Reduce noise from httpx/httpcore
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="EatFit24 AI Proxy")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    Request ID middleware (P1.1).

    - Takes X-Request-ID from incoming request or generates new UUID
    - Adds X-Request-ID to response headers
    - Stores in contextvars for logging
    """
    # Get or generate request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

    # Store in context variable for logging
    token = request_id_ctx.set(request_id)

    try:
        # Log request start
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "client_ip": client_ip,
            },
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
    finally:
        # Reset context variable
        request_id_ctx.reset(token)


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "ok"}


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}


@app.post("/api/v1/ai/recognize-food", response_model=RecognizeFoodResponse)
async def recognize_food(
    image: UploadFile = File(..., description="Food image file (JPEG/PNG)"),
    user_comment: Optional[str] = Form(
        None, description="Optional comment about the food"
    ),
    locale: str = Form("ru", description="Language locale (ru/en)"),
    api_key: str = Depends(verify_api_key),
):
    """
    Recognize food items in an image and return nutritional information.

    Args:
        image: Uploaded image file (JPEG or PNG format)
        user_comment: Optional comment describing the food
        locale: Language locale for response (default: "ru")
        api_key: API key for authentication (provided via X-API-Key header)

    Returns:
        RecognizeFoodResponse with food items, totals, and optional model notes

    Raises:
        HTTPException: 401 for invalid API key, 400 for bad requests,
                       413 for file too large, 500 for server/API errors
    """
    try:
        # Validate content type
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Unsupported file type: {image.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {image.content_type}. Only JPEG/PNG are allowed.",
            )

        # Read file content
        content = await image.read()

        # Validate file size
        file_size = len(content)
        if file_size == 0:
            logger.warning("Empty file uploaded")
            raise HTTPException(status_code=400, detail="Empty file.")

        if file_size > settings.max_image_size_bytes:
            logger.warning(
                f"File too large: {file_size} bytes (max: {settings.max_image_size_bytes})"
            )
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max allowed size is {settings.max_image_size_bytes} bytes ({settings.max_image_size_bytes // (1024 * 1024)} MB).",
            )

        logger.info(
            f"Processing food recognition - file: {image.filename}, size: {file_size}, type: {image.content_type}, locale: {locale}"
        )

        items, total, model_notes = await recognize_food_with_bytes(
            image_bytes=content,
            filename=image.filename or "image.jpg",
            content_type=image.content_type or "image/jpeg",
            user_comment=user_comment,
            locale=locale,
        )

        logger.info(f"Successfully recognized {len(items)} food items")

        return RecognizeFoodResponse(items=items, total=total, model_notes=model_notes)

    except OpenRouterError as e:
        logger.error(f"OpenRouter error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
