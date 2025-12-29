# app/schemas.py
from pydantic import BaseModel, model_serializer
from typing import List, Optional, Any


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


class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None
