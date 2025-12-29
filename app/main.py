# app/main.py
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

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def safe_log_message(record: logging.LogRecord) -> str:
    """Make formatter never crash on weird msg/args."""
    try:
        if isinstance(record.msg, (dict, list)):
            return json.dumps(record.msg, ensure_ascii=False)
        return record.getMessage()
    except Exception:
        try:
            return str(record.msg)
        except Exception:
            return repr(record.msg)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": safe_log_message(record),
        }

        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id

        for key in ("path", "method", "status", "duration_ms", "client_ip"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="EatFit24 AI Proxy")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    token = request_id_ctx.set(request_id)

    try:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "Request started",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "client_ip": client_ip,
            },
        )

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            "Request completed",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx.reset(token)


@app.get("/health")
async def health():
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
    try:
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Unsupported file type",
                extra={"path": "/api/v1/ai/recognize-food", "method": "POST"},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {image.content_type}. Only JPEG/PNG are allowed.",
            )

        content = await image.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file.")

        if file_size > settings.max_image_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max allowed size is {settings.max_image_size_bytes} bytes "
                f"({settings.max_image_size_bytes // (1024 * 1024)} MB).",
            )

        logger.info(
            "Processing food recognition",
            extra={
                "path": "/api/v1/ai/recognize-food",
                "method": "POST",
                "status": 0,
                "duration_ms": 0,
            },
        )

        items, total, model_notes = await recognize_food_with_bytes(
            image_bytes=content,
            filename=image.filename or "image.jpg",
            content_type=image.content_type or "image/jpeg",
            user_comment=user_comment,
            locale=locale,
        )

        logger.info("Recognition success", extra={"status": 200})
        return RecognizeFoodResponse(items=items, total=total, model_notes=model_notes)

    except OpenRouterError as e:
        logger.error("OpenRouter error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
