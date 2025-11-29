import logging
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from app.schemas import RecognizeFoodRequest, RecognizeFoodResponse
from app.openrouter_client import recognize_food_with_openrouter, OpenRouterError
from app.auth import verify_api_key

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


@app.post("/api/v1/ai/recognize-food", response_model=RecognizeFoodResponse)
async def recognize_food(
    payload: RecognizeFoodRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Recognize food items in an image and return nutritional information

    Args:
        payload: Request containing image_url, optional user_comment, and locale
        api_key: API key for authentication (provided via X-API-Key header)

    Returns:
        RecognizeFoodResponse with food items, totals, and optional model notes

    Raises:
        HTTPException: 401 for invalid API key, 400 for bad requests, 500 for server/API errors
    """
    try:
        logger.info(f"Processing food recognition request for image: {payload.image_url}")

        items, total, model_notes = await recognize_food_with_openrouter(
            image_url=str(payload.image_url),
            user_comment=payload.user_comment,
            locale=payload.locale
        )

        logger.info(f"Successfully recognized {len(items)} food items")

        return RecognizeFoodResponse(
            items=items,
            total=total,
            model_notes=model_notes
        )

    except OpenRouterError as e:
        logger.error(f"OpenRouter error for image {payload.image_url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error for image {payload.image_url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
