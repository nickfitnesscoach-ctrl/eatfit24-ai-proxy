from pydantic import BaseModel, Field
from typing import List, Optional

class FoodItem(BaseModel):
    name: str
    grams: float
    kcal: float = Field(alias="calories")  # Support both kcal and calories
    protein: float
    fat: float
    # F-004 FIX: Unified field name - use carbohydrates everywhere
    carbohydrates: float = Field(alias="carbs")  # Accept carbs, output carbohydrates
    
    class Config:
        populate_by_name = True  # Allow both field name and alias

class TotalNutrition(BaseModel):
    kcal: float = Field(alias="calories")
    protein: float
    fat: float
    carbohydrates: float = Field(alias="carbs")
    
    class Config:
        populate_by_name = True

class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None
