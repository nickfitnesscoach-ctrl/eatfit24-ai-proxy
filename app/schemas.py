from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class RecognizeFoodRequest(BaseModel):
    image_url: HttpUrl
    user_comment: Optional[str] = None
    locale: str = "ru"

class FoodItem(BaseModel):
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float

class TotalNutrition(BaseModel):
    kcal: float
    protein: float
    fat: float
    carbs: float

class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None
