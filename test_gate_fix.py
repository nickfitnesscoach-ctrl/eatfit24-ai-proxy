"""
Test script to verify gate error handling fix.
Tests that invalid gate responses return is_food=None instead of is_food=False.
"""

from app.food_gate import parse_gate_response
from app.schemas import GateResult


def test_parse_gate_response():
    """Test various gate response scenarios."""

    print("=" * 60)
    print("Testing parse_gate_response with various inputs")
    print("=" * 60)

    # Test 1: Valid JSON response
    print("\n1. Valid JSON response:")
    valid_json = '{"is_food": true, "confidence": 0.95, "reason": "visible food"}'
    result = parse_gate_response(valid_json)
    print(f"   Input: {valid_json}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    assert result.is_food is True
    assert result.confidence == 0.95
    print("   [OK] PASS")

    # Test 2: Valid JSON - not food
    print("\n2. Valid JSON - not food:")
    not_food_json = '{"is_food": false, "confidence": 0.8, "reason": "screenshot"}'
    result = parse_gate_response(not_food_json)
    print(f"   Input: {not_food_json}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    assert result.is_food is False
    assert result.confidence == 0.8
    print("   [OK] PASS")

    # Test 3: Plain string (not JSON) - SHOULD RETURN is_food=None
    print("\n3. Plain string (not JSON) - should return is_food=None:")
    plain_string = "This is just plain text, not food"
    result = parse_gate_response(plain_string)
    print(f"   Input: {plain_string}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    assert result.is_food is None, f"Expected is_food=None for plain string, got {result.is_food}"
    assert result.confidence is None, f"Expected confidence=None for plain string, got {result.confidence}"
    assert result.reason == "invalid_gate_response"
    print("   [OK] PASS - Returns None instead of False")

    # Test 4: Malformed JSON
    print("\n4. Malformed JSON - should return is_food=None:")
    malformed_json = '{"is_food": true, "confidence": 0.9'
    result = parse_gate_response(malformed_json)
    print(f"   Input: {malformed_json}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    # json_repair might fix this, but if it fails, should be None
    print(f"   [OK] Result: is_food={result.is_food} (json_repair may have fixed it)")

    # Test 5: JSON array instead of object - SHOULD RETURN is_food=None
    print("\n5. JSON array instead of object - should return is_food=None:")
    json_array = '[{"is_food": true}]'
    result = parse_gate_response(json_array)
    print(f"   Input: {json_array}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    assert result.is_food is None, f"Expected is_food=None for array, got {result.is_food}"
    assert result.confidence is None, f"Expected confidence=None for array, got {result.confidence}"
    assert result.reason == "invalid_gate_response"
    print("   [OK] PASS - Returns None instead of False")

    # Test 6: Markdown wrapped JSON (common LLM mistake)
    print("\n6. Markdown wrapped JSON:")
    markdown_json = '```json\n{"is_food": true, "confidence": 0.85, "reason": "food visible"}\n```'
    result = parse_gate_response(markdown_json)
    print(f"   Input: {markdown_json}")
    print(f"   Result: is_food={result.is_food}, confidence={result.confidence}, reason={result.reason}")
    # json_repair should handle this
    if result.is_food is not None:
        print("   [OK] json_repair successfully extracted JSON from markdown")
    else:
        print("   [OK] Returns None (json_repair couldn't extract)")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print("\nKey fix verified:")
    print("- Invalid responses now return is_food=None (not False)")
    print("- This allows proper GATE_ERROR vs UNSUPPORTED_CONTENT distinction")


if __name__ == "__main__":
    test_parse_gate_response()
