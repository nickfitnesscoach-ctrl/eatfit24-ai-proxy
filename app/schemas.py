# app/schemas.py
from pydantic import BaseModel, model_serializer
from typing import List, Optional, Any, Literal


class FoodItem(BaseModel):
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbohydrates: float

    @model_serializer
    def serialize_with_aliases(self) -> dict[str, Any]:
        # Base is SSOT (mode='python' prevents recursion)
        data = {
            "name": self.name,
            "grams": self.grams,
            "kcal": self.kcal,
            "protein": self.protein,
            "fat": self.fat,
            "carbohydrates": self.carbohydrates,
        }
        # Back-compat aliases
        data["amount_grams"] = self.grams
        data["calories"] = self.kcal
        data["carbs"] = self.carbohydrates
        return data


class TotalNutrition(BaseModel):
    kcal: float
    protein: float
    fat: float
    carbohydrates: float

    @model_serializer
    def serialize_with_aliases(self) -> dict[str, Any]:
        # Prevent recursion by using direct field access
        data = {
            "kcal": self.kcal,
            "protein": self.protein,
            "fat": self.fat,
            "carbohydrates": self.carbohydrates,
        }
        data["calories"] = self.kcal
        data["carbs"] = self.carbohydrates
        return data


# ==================================
# Gate Result (Anti-Hallucination)
# ==================================
class GateResult(BaseModel):
    """Result from food detection gate.

    If is_food is None, it means gate response was invalid/unparseable.
    This should be treated as GATE_ERROR, not as UNSUPPORTED_CONTENT.
    """

    is_food: Optional[bool]
    confidence: Optional[float]
    reason: str


# ==================================
# Recognition Result (inner payload)
# ==================================
class RecognitionResult(BaseModel):
    """Successful recognition payload."""

    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None


# ==================================
# Response Schemas
# ==================================


# Legacy response (for backward compat with existing clients)
class RecognizeFoodResponse(BaseModel):
    """Legacy response format - items/total at root level."""

    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None


class SuccessResponse(BaseModel):
    """New success response with gate info."""

    status: Literal["success"] = "success"
    is_food: bool
    confidence: float
    gate_reason: Optional[str] = None
    trace_id: str
    result: RecognitionResult


# Error codes supported by this proxy
ErrorCode = Literal[
    "UNSUPPORTED_CONTENT",  # Image has no food
    "EMPTY_RESULT",  # Food detected but recognition failed
    "INVALID_IMAGE",  # Image cannot be decoded/read
    "UNSUPPORTED_IMAGE_FORMAT",  # Content-type not in allowlist
    "IMAGE_TOO_LARGE",  # Exceeds max size
    "GATE_ERROR",  # Gate returned invalid/unparseable response
    "UPSTREAM_ERROR",  # AI provider error
    "UPSTREAM_TIMEOUT",  # AI provider timeout
    "RATE_LIMIT",  # Rate limited by AI provider
]


class ErrorResponse(BaseModel):
    """
    Structured error response compatible with backend Error Contract.
    """

    status: Literal["error"] = "error"
    error_code: ErrorCode
    user_title: str
    user_message: str
    user_actions: List[str]
    allow_retry: bool
    trace_id: str
    # Legacy backward-compat fields
    error: Optional[str] = None
    error_message: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-populate legacy fields if not set
        if self.error is None:
            object.__setattr__(self, "error", self.error_code)
        if self.error_message is None:
            object.__setattr__(self, "error_message", self.user_message)


# ==================================
# Error Definitions (SSOT)
# ==================================
ERROR_DEFINITIONS: dict[str, dict] = {
    "UNSUPPORTED_CONTENT": {
        "http_status": 400,
        "user_title": "Похоже, на фото не еда",
        "user_message": "Сфотографируйте блюдо крупнее при хорошем освещении.",
        "user_actions": ["retake"],
        "allow_retry": False,
    },
    "EMPTY_RESULT": {
        "http_status": 400,
        "user_title": "Не удалось распознать блюдо",
        "user_message": "Попробуйте сфотографировать еду ближе при хорошем освещении.",
        "user_actions": ["retake"],
        "allow_retry": False,
    },
    "INVALID_IMAGE": {
        "http_status": 400,
        "user_title": "Некорректное изображение",
        "user_message": "Не удалось прочитать файл. Попробуйте другое фото.",
        "user_actions": ["retake"],
        "allow_retry": False,
    },
    "UNSUPPORTED_IMAGE_FORMAT": {
        "http_status": 400,
        "user_title": "Неподдерживаемый формат",
        "user_message": "Поддерживаются только JPEG и PNG.",
        "user_actions": ["retake"],
        "allow_retry": False,
    },
    "IMAGE_TOO_LARGE": {
        "http_status": 413,
        "user_title": "Файл слишком большой",
        "user_message": "Максимальный размер — 5 МБ.",
        "user_actions": ["retake"],
        "allow_retry": False,
    },
    "GATE_ERROR": {
        "http_status": 502,
        "user_title": "Ошибка проверки изображения",
        "user_message": "Не удалось проверить содержимое изображения. Попробуйте ещё раз.",
        "user_actions": ["retry"],
        "allow_retry": True,
    },
    "UPSTREAM_ERROR": {
        "http_status": 502,
        "user_title": "Ошибка сервиса распознавания",
        "user_message": "Попробуйте ещё раз через несколько секунд.",
        "user_actions": ["retry"],
        "allow_retry": True,
    },
    "UPSTREAM_TIMEOUT": {
        "http_status": 504,
        "user_title": "Сервис не отвечает",
        "user_message": "Попробуйте ещё раз.",
        "user_actions": ["retry"],
        "allow_retry": True,
    },
    "RATE_LIMIT": {
        "http_status": 429,
        "user_title": "Слишком много запросов",
        "user_message": "Подождите немного и попробуйте снова.",
        "user_actions": ["retry"],
        "allow_retry": True,
    },
}
