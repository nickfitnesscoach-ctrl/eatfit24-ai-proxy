from pydantic import BaseModel, Field
from typing import List, Optional

class FoodItem(BaseModel):
    """
    Food item with nutritional information.
    
    Field naming:
    - Internal (Python): kcal, carbohydrates
    - Serialization output: kcal, carbohydrates (by_alias=False by default)
    - Accepts input: both kcal/calories, both carbohydrates/carbs
    """
    name: str
    grams: float
    kcal: float  # Калории - используем kcal как основное имя
    protein: float
    fat: float
    carbohydrates: float  # Углеводы - используем carbohydrates как основное имя
    
    class Config:
        populate_by_name = True  # Allow both field name and alias

class TotalNutrition(BaseModel):
    """Total nutrition values."""
    kcal: float
    protein: float
    fat: float
    carbohydrates: float
    
    class Config:
        populate_by_name = True

class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None
