# Smoke Tests for AI Proxy

## Purpose

This checklist MUST be validated whenever:
- Gate prompt is modified
- Confidence thresholds are changed (`FOOD_GATE_MIN_THRESHOLD`, `FOOD_GATE_MED_THRESHOLD`)
- Recognition prompt is modified

Failure on any of these tests indicates a **regression** that must be fixed before deployment.

---

## Critical Test Cases

### ✅ MUST PASS (Food Recognition)

These images MUST NOT return `UNSUPPORTED_CONTENT` or `NOT_FOOD`:

1. **Single fruit without context**
   - Example: One apple/pear/banana on white background
   - Expected: Gate `is_food=true`, Recognition returns item
   - **Why critical:** Most common false negative

2. **Single vegetable without context**
   - Example: One tomato/cucumber/carrot on table
   - Expected: Gate `is_food=true`, Recognition returns item
   - **Why critical:** Common user scenario (vegetable tracking)

3. **Food in hand**
   - Example: Nuts, berries, or crackers in palm
   - Expected: Gate `is_food=true`
   - **Why critical:** Mobile app usage pattern

4. **Packaged food product**
   - Example: Yogurt cup, protein bar, milk carton
   - Expected: Gate `is_food=true`
   - **Why critical:** Common tracking scenario

---

### ❌ MUST REJECT (Not Food)

These images MUST return `UNSUPPORTED_CONTENT` (gate confidence < 0.25):

5. **Human face**
   - Example: Selfie, portrait photo
   - Expected: `is_food=false` or confidence < 0.25
   - **Why critical:** Privacy and hallucination prevention

6. **Blank wall or room**
   - Example: Empty room, wall, floor
   - Expected: `is_food=false` or confidence < 0.25
   - **Why critical:** User accidentally opened camera

7. **Screenshot of text**
   - Example: Chat screenshot, article, code
   - Expected: `is_food=false` or confidence < 0.25
   - **Why critical:** User uploaded wrong file

8. **Document or receipt**
   - Example: Bill, receipt, paper document
   - Expected: `is_food=false` or confidence < 0.25
   - **Why critical:** User confusion prevention

---

## Acceptable Degradation

These are **NOT regressions** (expected behavior after fail-open changes):

### Low Confidence Passthrough (OK)

- Wall with slight texture → Gate `is_food=true, confidence=0.35` → Recognition `items=[]` → `LOW_CONFIDENCE`
- Blurry ambiguous photo → Gate `is_food=true, confidence=0.40` → Recognition `items=[]` → `LOW_CONFIDENCE`

**Why acceptable:** User gets helpful error ("choose manually or retake") instead of hard rejection.

### Edge Cases (Monitor, Don't Block)

- **Live animal** (e.g., chicken, fish swimming): May pass gate with low confidence
  - Expected: Gate might say `is_food=true, confidence=0.30-0.50`
  - Outcome: `LOW_CONFIDENCE` → User can clarify intent
  - **Not a regression** as long as it's not recognized as cooked food

---

## How to Run

### Manual Testing (Quick)

```bash
# Start local server
uvicorn app.main:app --reload --port 8001

# Test with curl
curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: your-secret" \
  -F "image=@test_images/single_apple.jpg" \
  -F "locale=ru"
```

### Automated Testing (Recommended)

```bash
# If test images exist in tests/smoke_images/
python tests/test_smoke.py
```

---

## Success Criteria

**Before deploying prompt/threshold changes:**

- ✅ All 4 "MUST PASS" cases succeed (not UNSUPPORTED_CONTENT)
- ✅ All 4 "MUST REJECT" cases fail appropriately (UNSUPPORTED_CONTENT)
- ✅ No hallucinations on non-food images (check `items` field)

**Post-deployment monitoring (first 24h):**

- Gate pass rate: Should increase by 10-20% (more permissive)
- LOW_CONFIDENCE rate: Expected to appear (new error code)
- User complaints about false positives: Should remain stable (< 5% increase)

---

## Regression Examples (Historical)

**Example 1:** Gate prompt change from "Could this be food?" → "Is this clearly food?"
- **Symptom:** Single fruits started failing
- **Root cause:** Word "clearly" introduced fail-closed bias
- **Fix:** Reverted to permissive wording

**Example 2:** Threshold raised from 0.40 → 0.70
- **Symptom:** Vegetables without plates rejected
- **Root cause:** Threshold too strict for low-context images
- **Fix:** Lowered to 0.55 with confidence bands

---

## Contact

If smoke tests fail after your change:
1. Do NOT deploy
2. Review [docs/AI_PROXY_GATE.md](AI_PROXY_GATE.md) for gate philosophy
3. Check git history: `git log --oneline app/food_gate.py app/config.py`
4. Consult architectural invariant in [app/food_gate.py](../app/food_gate.py)
