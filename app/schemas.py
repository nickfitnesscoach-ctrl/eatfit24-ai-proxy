from pydantic import BaseModel
from typing import List, Optional

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
