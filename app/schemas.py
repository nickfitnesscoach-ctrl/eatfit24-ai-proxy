from pydantic import BaseModel, model_serializer
from typing import List, Optional, Any


class FoodItem(BaseModel):
    """
    Food item with nutritional information.

    Field naming:
    - Internal (Python): kcal, grams, carbohydrates
    - Serialization output: includes BOTH formats for compatibility:
      - kcal AND calories (same value)
      - grams AND amount_grams (same value)
      - carbohydrates AND carbs (same value)
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

    @model_serializer
    def serialize_with_aliases(self) -> dict[str, Any]:
        """Serialize with both original and alias field names for compatibility."""
        return {
            "name": self.name,
            "grams": self.grams,
            "amount_grams": self.grams,  # Alias for backend compatibility
            "kcal": self.kcal,
            "calories": self.kcal,  # Alias for frontend compatibility
            "protein": self.protein,
            "fat": self.fat,
            "carbohydrates": self.carbohydrates,
            "carbs": self.carbohydrates,  # Short alias
        }


class TotalNutrition(BaseModel):
    """Total nutrition values."""

    kcal: float
    protein: float
    fat: float
    carbohydrates: float

    class Config:
        populate_by_name = True

    @model_serializer
    def serialize_with_aliases(self) -> dict[str, Any]:
        """Serialize with both original and alias field names for compatibility."""
        return {
            "kcal": self.kcal,
            "calories": self.kcal,  # Alias for frontend compatibility
            "protein": self.protein,
            "fat": self.fat,
            "carbohydrates": self.carbohydrates,
            "carbs": self.carbohydrates,  # Short alias
        }


class RecognizeFoodResponse(BaseModel):
    items: List[FoodItem]
    total: TotalNutrition
    model_notes: Optional[str] = None
