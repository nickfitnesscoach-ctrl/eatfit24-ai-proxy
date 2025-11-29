# EatFit24 AI Proxy

8:@>A5@28A, :>B>@K9 ?@8=8<05B D>B> 54K (?> URL) 8 >?F8>=0;L=K9 :><<5=B0@89 ?>;L7>20B5;O,
2K7K205B 2=5H=NN AI-<>45;L (OpenRouter) 8 2>72@0I05B AB@C:BC@C A ?@>4C:B0<8 8 #.

## !B5:
- Python 3.12+
- FastAPI
- Uvicorn
- httpx

## KAB@K9 AB0@B

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## -=4?>8=BK

**GET /health**  ?@>25@:0 A>AB>O=8O.

**POST /api/v1/ai/recognize-food**  >A=>2=>9 AI-M=4?>8=B.

### @8<5@ 70?@>A0

```bash
curl -X POST http://127.0.0.1:8001/api/v1/ai/recognize-food \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/food.jpg",
    "user_comment": "-B> 3@5G:0 A :C@8F59",
    "locale": "ru"
  }'
```

### @8<5@ >B25B0

```json
{
  "items": [
    {
      "name": "@5G:0 >B20@=0O",
      "grams": 150.0,
      "kcal": 165.0,
      "protein": 6.0,
      "fat": 1.5,
      "carbs": 30.0
    },
    {
      "name": "C@8=0O 3@C4:0",
      "grams": 100.0,
      "kcal": 165.0,
      "protein": 31.0,
      "fat": 3.6,
      "carbs": 0.0
    }
  ],
  "total": {
    "kcal": 330.0,
    "protein": 37.0,
    "fat": 5.1,
    "carbs": 30.0
  },
  "model_notes": " 0A?>7=0=> =0 >A=>25 87>1@065=8O 8 :><<5=B0@8O ?>;L7>20B5;O"
}
```

## 5@5<5==K5 >:@C65=8O

!>7409B5 D09; `.env` =0 >A=>25 `.env.example`:

```
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

##  07@01>B:0

!5@25@ 02B><0B8G5A:8 ?5@5703@C605BAO ?@8 87<5=5=88 :>40 1;03>40@O D;03C `--reload`.
