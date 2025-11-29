from fastapi import FastAPI, HTTPException
from app.schemas import RecognizeFoodRequest, RecognizeFoodResponse, TotalNutrition

app = FastAPI(title="EatFit24 AI Proxy")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/ai/recognize-food", response_model=RecognizeFoodResponse)
async def recognize_food(payload: RecognizeFoodRequest):
    try:
        # Временный stub-ответ
        return RecognizeFoodResponse(
            items=[],
            total=TotalNutrition(kcal=0, protein=0, fat=0, carbs=0),
            model_notes="Stub response. OpenRouter not connected yet."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
