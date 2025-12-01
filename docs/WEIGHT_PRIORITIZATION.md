# Weight Prioritization System

## Overview

The AI proxy now implements a weight prioritization system that treats user-provided weights in comments as the primary source of truth, with the image serving as a verification tool.

## Changes Made

### 1. Weight Detection Pattern

Added a regex pattern to detect explicit weight measurements:

```python
GRAMS_PATTERN = re.compile(r"\b\d+\s*(г|гр|g)\b", re.IGNORECASE)
```

This pattern detects:
- Russian formats: "150 г", "200 гр", "100г"
- English formats: "150 g", "200 G"

### 2. Helper Function

Added `has_explicit_grams()` function to check if user comment contains weight measurements:

```python
def has_explicit_grams(user_comment: str | None) -> bool:
    """
    Check if user comment contains explicit weight measurements

    Returns:
        True if comment contains weight measurements like "150 г", "200 g"
    """
```

### 3. Enhanced Prompt Template

The `build_food_recognition_prompt()` function now generates context-aware prompts that:

#### When user provides weights (e.g., "Индейка 150 г, картофель 200 г"):

1. **Prioritizes user weights** - These are treated as the source of truth
2. **Uses photo for verification** - Checks if the food items actually match
3. **Prevents weight changes** - Model is instructed NOT to modify weights unless there's explicit contradiction
4. **Reports doubts** - If uncertain, model keeps user weights and reports concerns in `model_notes`

#### When user comment has NO weights:

- Model determines composition from comment + photo
- Estimates weights from photo
- Works as before

#### When comment is empty:

- Model works from photo only
- Identifies all visible food items
- Estimates weights based on image

## Prompt Structure

### Russian Locale (locale="ru")

```
Ты — эксперт по питанию и взвешиванию порций. У тебя есть:
1) ФОТО блюда.
2) КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ с описанием и весами продуктов.

=== КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ ===
{user_comment or "Комментарий отсутствует"}
================================

⚠️ ВАЖНО: ПОЛЬЗОВАТЕЛЬ УКАЗАЛ ТОЧНЫЕ ВЕСА ПРОДУКТОВ — НЕ ИЗМЕНЯЙ ИХ БЕЗ ЯВНОГО ПРОТИВОРЕЧИЯ С ФОТО.
(only shown when weights detected)

ПРАВИЛА РАБОТЫ:
[detailed rules...]
```

### English Locale (locale="en")

Similar structure but in English with appropriate formatting.

## API Usage

No changes to the API endpoint or request/response format. The system works transparently:

```python
# POST /api/v1/ai/recognize-food
{
  "image": <file>,
  "user_comment": "Индейка 150 г, картофель 200 г",  # Optional
  "locale": "ru"  # Optional, default "ru"
}
```

## Testing

Run the test script to verify functionality:

```bash
python test_prompt.py
```

This will generate `test_output.txt` showing how prompts are generated for different scenarios:

1. Comment with explicit weights
2. Comment without weights
3. Empty comment
4. English locale with weights
5. Various weight format recognition

## Acceptance Criteria

✅ **Scenario 1 - Weights in comment**
- Input: "Индейка 150 г, картофель 200 г" + matching photo
- Expected: Items show grams ≈ 150 for turkey, ≈ 200 for potatoes
- No phrases like "I re-estimated weights" in model_notes

✅ **Scenario 2 - No weights in comment**
- Input: "гречка с курицей" + photo
- Expected: Composition from comment + photo, weights estimated by model

✅ **Scenario 3 - Empty comment**
- Input: null/empty comment + photo
- Expected: Full analysis from photo only

## Implementation Files

Modified files:
- [app/openrouter_client.py](../app/openrouter_client.py) - Main logic implementation
  - Line 13: Added `GRAMS_PATTERN` regex
  - Lines 21-33: Added `has_explicit_grams()` helper
  - Lines 36-186: Rewrote `build_food_recognition_prompt()` with new logic

Test files:
- [test_prompt.py](../test_prompt.py) - Test script for verification
- [test_output.txt](../test_output.txt) - Generated test results

## Benefits

1. **User control** - Users can override AI estimates with their own measurements
2. **Trust in data** - User-provided weights are preserved, building user confidence
3. **Smart verification** - Photo still used to catch obvious errors
4. **Transparency** - Model reports doubts in `model_notes` instead of silently changing values
5. **Backward compatible** - Works seamlessly with existing API without breaking changes
