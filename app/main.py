# app/main.py
import logging
import time
import json
import uuid
import sys
import math
from contextvars import ContextVar
from typing import Optional, Union

from fastapi import FastAPI, Request, File, UploadFile, Form, Depends
from fastapi.responses import JSONResponse

from app.schemas import (
    SuccessResponse,
    ErrorResponse,
    RecognitionResult,
    ERROR_DEFINITIONS,
)
from app.openrouter_client import recognize_food_with_bytes, OpenRouterError
from app.food_gate import check_food_gate
from app.auth import verify_api_key
from app.config import settings

# Context var for request/trace ID
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
            log_data["trace_id"] = req_id

        for key in (
            "path",
            "method",
            "status",
            "duration_ms",
            "client_ip",
            "gate.is_food",
            "gate.confidence",
            "final_status",
            "error_code",
        ):
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


# ==================================
# Middleware
# ==================================
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # Accept X-Trace-Id (SSOT) or X-Request-ID for compat
    trace_id = (
        request.headers.get("X-Trace-Id")
        or request.headers.get("X-Request-ID")
        or uuid.uuid4().hex
    )
    token = request_id_ctx.set(trace_id)

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

        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        request_id_ctx.reset(token)


# ==================================
# Health Check
# ==================================
@app.get("/health")
async def health():
    return {"status": "ok"}


# ==================================
# Helpers
# ==================================
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}


def make_error_response(
    error_code: str,
    trace_id: str,
    custom_message: Optional[str] = None,
) -> tuple[dict, int]:
    """Build error response dict and HTTP status code."""
    defn = ERROR_DEFINITIONS.get(error_code, ERROR_DEFINITIONS["UPSTREAM_ERROR"])

    http_status = 200 if settings.error_http200_compat else defn["http_status"]

    response = ErrorResponse(
        error_code=error_code,
        user_title=defn["user_title"],
        user_message=custom_message or defn["user_message"],
        user_actions=defn["user_actions"],
        allow_retry=defn["allow_retry"],
        trace_id=trace_id,
    )

    return response.model_dump(), http_status


def validate_recognition_result(items: list, total) -> bool:
    """
    Return True if result is valid (non-empty), False triggers EMPTY_RESULT.
    """
    if not items:
        return False
    if total is None:
        return False
    if hasattr(total, "kcal"):
        if total.kcal is None:
            return False
        if isinstance(total.kcal, float) and math.isnan(total.kcal):
            return False
    return True


# ==================================
# Main Endpoint
# ==================================
@app.post(
    "/api/v1/ai/recognize-food",
    response_model=Union[SuccessResponse, ErrorResponse],
    responses={
        200: {"model": SuccessResponse},
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def recognize_food(
    request: Request,
    image: UploadFile = File(..., description="Food image file (JPEG/PNG)"),
    user_comment: Optional[str] = Form(
        None, description="Optional comment about the food"
    ),
    locale: str = Form("ru", description="Language locale (ru/en)"),
    api_key: str = Depends(verify_api_key),
):
    trace_id = request_id_ctx.get()

    try:
        # ============================
        # 1. Validate image format
        # ============================
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Unsupported file type",
                extra={
                    "path": "/api/v1/ai/recognize-food",
                    "method": "POST",
                    "error_code": "UNSUPPORTED_IMAGE_FORMAT",
                },
            )
            body, status = make_error_response("UNSUPPORTED_IMAGE_FORMAT", trace_id)
            return JSONResponse(status_code=status, content=body)

        # Read image content
        try:
            content = await image.read()
        except Exception as e:
            logger.error("Failed to read image: %s", str(e))
            body, status = make_error_response("INVALID_IMAGE", trace_id)
            return JSONResponse(status_code=status, content=body)

        file_size = len(content)

        # ============================
        # 2. Validate image size
        # ============================
        if file_size == 0:
            body, status = make_error_response(
                "INVALID_IMAGE", trace_id, "Пустой файл."
            )
            return JSONResponse(status_code=status, content=body)

        if file_size > settings.max_image_size_bytes:
            body, status = make_error_response("IMAGE_TOO_LARGE", trace_id)
            return JSONResponse(status_code=status, content=body)

        try:
            # ============================
            # 3. Food Gate Check
            # ============================
            logger.info("Running food gate check")
            gate_result = await check_food_gate(
                image_bytes=content,
                content_type=image.content_type or "image/jpeg",
                locale=locale,
            )

            logger.info(
                "Gate result",
                extra={
                    "gate.is_food": gate_result.is_food,
                    "gate.confidence": gate_result.confidence,
                },
            )

            # Check if gate response was invalid (is_food=None means parse error)
            if gate_result.is_food is None:
                logger.warning(
                    "Gate returned invalid response",
                    extra={
                        "final_status": "error",
                        "error_code": "GATE_ERROR",
                        "gate.reason": gate_result.reason,
                    },
                )
                body, status = make_error_response("GATE_ERROR", trace_id)
                return JSONResponse(status_code=status, content=body)

            # Gate decision with confidence bands:
            # < MIN → NOT_FOOD
            # MIN to MED → LOW_CONFIDENCE (run recognition, but may fail gracefully)
            # > MED → FOOD_LIKELY (confident, proceed normally)
            confidence = gate_result.confidence if gate_result.confidence is not None else 0.0

            if not gate_result.is_food or confidence < settings.food_gate_min_threshold:
                # Definitely not food
                logger.info(
                    "Gate rejected: not food",
                    extra={
                        "final_status": "error",
                        "error_code": "UNSUPPORTED_CONTENT",
                        "gate.is_food": gate_result.is_food,
                        "gate.confidence": confidence,
                    },
                )
                body, status = make_error_response("UNSUPPORTED_CONTENT", trace_id)
                return JSONResponse(status_code=status, content=body)

            # Track if we're in low confidence zone (0.25-0.55)
            is_low_confidence_zone = confidence < settings.food_gate_med_threshold

            # ============================
            # 4. Main Recognition
            # ============================
            logger.info(
                "Gate passed, running main recognition",
                extra={
                    "gate.confidence": confidence,
                    "low_confidence_zone": is_low_confidence_zone,
                },
            )

            items, total, model_notes = await recognize_food_with_bytes(
                image_bytes=content,
                filename=image.filename or "image.jpg",
                content_type=image.content_type or "image/jpeg",
                user_comment=user_comment,
                locale=locale,
            )
        except OpenRouterError as e:
            error_str = str(e).lower()
            if "timeout" in error_str:
                error_code = "UPSTREAM_TIMEOUT"
            elif "rate" in error_str or "429" in error_str:
                error_code = "RATE_LIMIT"
            else:
                error_code = "UPSTREAM_ERROR"

            logger.error(
                "Recognition failed: %s",
                str(e),
                extra={"final_status": "error", "error_code": error_code},
            )
            body, status = make_error_response(error_code, trace_id)
            return JSONResponse(status_code=status, content=body)

        # ============================
        # 5. Post-Validation
        # ============================
        if not validate_recognition_result(items, total):
            # Recognition failed (empty items)
            # Choose error code based on gate confidence zone
            if is_low_confidence_zone:
                # Low confidence gate → suggest manual selection
                error_code = "LOW_CONFIDENCE"
            else:
                # High confidence gate but recognition failed → EMPTY_RESULT
                error_code = "EMPTY_RESULT"

            logger.info(
                "Recognition returned empty result",
                extra={
                    "final_status": "error",
                    "error_code": error_code,
                    "gate.is_food": gate_result.is_food,
                    "gate.confidence": confidence,
                    "low_confidence_zone": is_low_confidence_zone,
                },
            )
            body, status = make_error_response(error_code, trace_id)
            return JSONResponse(status_code=status, content=body)

        # ============================
        # 6. Success Response
        # ============================
        logger.info(
            "Recognition success",
            extra={
                "final_status": "success",
                "gate.is_food": gate_result.is_food,
                "gate.confidence": gate_result.confidence,
                "items_count": len(items),
            },
        )

        response = SuccessResponse(
            is_food=True,
            confidence=gate_result.confidence if gate_result.confidence is not None else 0.0,
            gate_reason=gate_result.reason,
            trace_id=trace_id,
            result=RecognitionResult(
                items=items,
                total=total,
                model_notes=model_notes,
            ),
        )

        return JSONResponse(status_code=200, content=response.model_dump())

    except Exception as e:
        logger.error(
            "Unexpected error: %s",
            str(e),
            exc_info=True,
            extra={"final_status": "error", "error_code": "UPSTREAM_ERROR"},
        )
        body, status = make_error_response("UPSTREAM_ERROR", trace_id)
        return JSONResponse(status_code=status, content=body)
