# Model Selection Guide

## TL;DR - Recommended Configuration

```env
# Main recognition model
OPENROUTER_MODEL=openai/gpt-4o-mini

# Gate model (optional, defaults to main model if not set)
OPENROUTER_GATE_MODEL=openai/gpt-4o-mini
```

For cost optimization, you can use the same model for both gate and recognition.

---

## Understanding the Architecture

AI Proxy uses **two separate model calls** for each food recognition request:

1. **Gate Check** (Anti-Hallucination)
   - **Purpose:** Quickly determine if the image contains food
   - **Requirements:** Vision support, JSON mode support, speed
   - **Tokens:** ~50-100 tokens per request
   - **Model:** `OPENROUTER_GATE_MODEL` (or `OPENROUTER_MODEL` if not set)

2. **Main Recognition**
   - **Purpose:** Detailed nutritional analysis if gate passes
   - **Requirements:** Vision support, accurate nutritional knowledge
   - **Tokens:** ~500-1000 tokens per request
   - **Model:** `OPENROUTER_MODEL`

---

## Model Requirements

### Gate Model Requirements

**MUST have:**
- ✅ Vision support (image analysis)
- ✅ JSON mode support (`response_format: json_object`)
- ✅ Fast response time (<2 seconds)

**Good to have:**
- Low cost per token
- High rate limits

### Main Recognition Model Requirements

**MUST have:**
- ✅ Vision support (image analysis)
- ✅ Strong reasoning (nutritional estimation)
- ✅ Multilingual support (Russian + English)

**Good to have:**
- JSON mode support (improves parsing)
- Instruction following

---

## Recommended Models

### Option 1: Cost-Optimized (Recommended)

```env
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_GATE_MODEL=openai/gpt-4o-mini
```

**Pros:**
- ✅ Single model = simpler configuration
- ✅ Excellent JSON mode support
- ✅ Fast response times
- ✅ Low cost (~$0.15 per 1M input tokens)
- ✅ High rate limits

**Cons:**
- Slightly more expensive than Gemini

**Best for:** Most use cases, production

---

### Option 2: Speed-Optimized

```env
OPENROUTER_MODEL=google/gemini-2.0-flash-exp
OPENROUTER_GATE_MODEL=openai/gpt-4o-mini
```

**Pros:**
- ✅ Very fast main recognition
- ✅ Free tier available for Gemini (with limits)
- ✅ GPT-4o-mini gate is reliable

**Cons:**
- Gemini may not support `response_format: json_object` consistently
- Requires two different model configurations

**Best for:** High-volume scenarios, testing

---

### Option 3: Premium Quality

```env
OPENROUTER_MODEL=openai/gpt-4o
OPENROUTER_GATE_MODEL=openai/gpt-4o-mini
```

**Pros:**
- ✅ Best nutritional accuracy
- ✅ Best instruction following
- ✅ Cheap gate check

**Cons:**
- ❌ 10x more expensive than gpt-4o-mini for main recognition
- Slower response times

**Best for:** High-accuracy requirements, low volume

---

## Models to AVOID

### ❌ `openai/gpt-5-image-mini`

**Problem:** This is an **image generation model**, not vision analysis.

```
Modality: text+image -> text+image (WRONG)
```

**Symptom:** Gate returns empty strings, causes `GATE_ERROR`

**Fix:** Use `openai/gpt-4o-mini` or `google/gemini-2.0-flash-exp`

---

### ❌ Text-only models

Any model without vision support will fail:
- `openai/gpt-3.5-turbo` ❌
- `anthropic/claude-3-haiku` ❌ (no vision on OpenRouter)
- `meta-llama/llama-3.1-8b-instruct` ❌

**Required modality:** `text+image -> text` ✅

---

## Cost Comparison

Estimated cost per 1000 requests (assuming avg 100 tokens gate + 500 tokens recognition):

| Configuration | Gate Cost | Recognition Cost | Total |
|---------------|-----------|------------------|-------|
| gpt-4o-mini / gpt-4o-mini | $0.015 | $0.075 | **$0.09** |
| gpt-4o-mini / gpt-4o | $0.015 | $0.75 | **$0.765** |
| gemini-2.0-flash / gpt-4o-mini | $0.00* | $0.075 | **$0.075** |

*Free tier limits apply

---

## Troubleshooting

### Error: `GATE_ERROR` with empty raw_preview

**Cause:** Gate model doesn't support vision or returns invalid response

**Fix:** Check model configuration:
```bash
# On server
cat /opt/eatfit24-ai-proxy/.env | grep OPENROUTER_MODEL

# Should be a vision model like:
OPENROUTER_MODEL=openai/gpt-4o-mini
```

---

### Error: Gate returns plain text instead of JSON

**Cause:** Model doesn't support `response_format: json_object`

**Fix:** Use a model with JSON mode support (gpt-4o-mini, gpt-4o)

---

### Error: Nutritional values are inaccurate

**Cause:** Main recognition model may not have good nutritional knowledge

**Fix:** Upgrade to `openai/gpt-4o` or add more detailed prompts

---

## Checking Available Models

To see all available vision models on OpenRouter:

```bash
curl -s https://openrouter.ai/api/v1/models \
  | jq '.data[] | select(.architecture.modality | contains("image->text")) | {id, name, modality: .architecture.modality}'
```

Filter for models with `response_format` support:
```bash
curl -s https://openrouter.ai/api/v1/models \
  | jq '.data[] | select(.architecture.modality | contains("image->text")) | select(.supports_structured_output == true) | .id'
```

---

## Configuration Validation

When you start the service, check logs for model configuration:

```bash
docker logs eatfit24-ai-proxy --tail=50 | grep "Settings loaded"
```

Should show:
```
Settings loaded: model=openai/gpt-4o-mini base_url=https://openrouter.ai/api/v1 ...
```

---

## Best Practices

1. **Use the same model for both** unless you have specific cost/performance requirements
2. **Always use vision models** - check modality includes "image"
3. **Prefer models with JSON mode** - reduces parsing errors
4. **Test with real food images** before deploying
5. **Monitor costs** - set up OpenRouter budget alerts

---

## Future Improvements

Potential optimizations:
- Add model fallback logic (if primary fails, try backup)
- Cache gate results for similar images
- Use smaller models for simple foods
- Batch processing for multiple images
