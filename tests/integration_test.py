# tests/integration_test.py
"""
Manual integration tests for Anti-Hallucination Gate.

Requires:
- Running AI Proxy server
- TEST_API_KEY or API_PROXY_SECRET env var
- Test images in tests/assets/

Run:
    python tests/integration_test.py
"""

import os
import sys
from pathlib import Path
import requests
import json

API_URL = os.environ.get(
    "TEST_API_URL", "http://localhost:8001/api/v1/ai/recognize-food"
)
API_KEY = os.environ.get("TEST_API_KEY") or os.environ.get("API_PROXY_SECRET")

ASSETS_DIR = Path(__file__).parent / "assets"


def print_result(name: str, response: requests.Response):
    """Pretty print test result."""
    print(f"\n{'=' * 60}")
    print(f"TEST: {name}")
    print(f"{'=' * 60}")
    print(f"Status Code: {response.status_code}")
    print(f"Headers: X-Trace-Id = {response.headers.get('X-Trace-Id', 'N/A')}")
    print("\nResponse:")
    try:
        import json

        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(response.text[:500])


def check_auth_error(response_code: int, body: dict) -> bool:
    """Check for auth/upstream errors and skip if found."""
    # Check if we got an explicit upstream error code
    error_code = body.get("error_code")
    if error_code in ["UPSTREAM_ERROR", "UPSTREAM_TIMEOUT", "RATE_LIMIT"]:
        print(f"\n⚠️  SKIP: Upstream Issue ({error_code})")
        print("   Check API Key, Credits, or Service Status")
        return True

    # Check raw HTTP codes that imply upstream failure
    if response_code in [502, 503, 504]:
        print(f"\n⚠️  SKIP: Upstream Server Error ({response_code})")
        return True

    return False


def test_normal_food():
    """Test with normal food image - should return success."""
    image_path = ASSETS_DIR / "test_food_image.jpg"
    if not image_path.exists():
        print(f"SKIP: {image_path} not found")
        return

    with open(image_path, "rb") as img:
        files = {"image": ("test.jpg", img, "image/jpeg")}
        data = {"locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        try:
            response = requests.post(
                API_URL, files=files, data=data, headers=headers, timeout=60
            )
        except Exception as e:
            print(f"\n❌ FAIL: Request failed: {e}")
            return

    print_result("Normal Food Image", response)

    body = response.json()
    if check_auth_error(response.status_code, body):
        return

    # Verify expectations
    if response.status_code == 200:
        if body.get("status") == "success":
            print("\n✅ PASS: Got success response with food detected")
            print(f"   is_food: {body.get('is_food')}")
            print(f"   confidence: {body.get('confidence')}")
            print(f"   items_count: {len(body.get('result', {}).get('items', []))}")
        else:
            print(f"\n❌ FAIL: Expected success, got {body.get('status')}")
    elif body.get("error_code") == "UNSUPPORTED_CONTENT":
        print("\n❌ FAIL: Gate rejected normal food (False Positive)")
        print(f"   Confidence: {body.get('gate.confidence', 'N/A')}")
    else:
        print(f"\n❌ FAIL: Expected 200, got {response.status_code}")


def test_not_food():
    """Test with non-food image - should return UNSUPPORTED_CONTENT."""
    image_path = ASSETS_DIR / "not_food.jpg"
    if not image_path.exists():
        print(f"\nSKIP: {image_path} not found")
        return

    with open(image_path, "rb") as img:
        files = {"image": ("not_food.jpg", img, "image/jpeg")}
        data = {"locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        try:
            response = requests.post(
                API_URL, files=files, data=data, headers=headers, timeout=60
            )
        except Exception as e:
            print(f"\n❌ FAIL: Request failed: {e}")
            return

    print_result("Not Food Image", response)

    body = response.json()
    if check_auth_error(response.status_code, body):
        return

    # Verify expectations
    if body.get("error_code") == "UNSUPPORTED_CONTENT":
        print("\n✅ PASS: Got UNSUPPORTED_CONTENT as expected")
        print(f"   allow_retry: {body.get('allow_retry')}")
        print(f"   user_actions: {body.get('user_actions')}")
    else:
        print(
            f"\n❌ FAIL: Expected UNSUPPORTED_CONTENT, got {body.get('error_code', body.get('status'))}"
        )


def test_blurry_food():
    """Test with blurry/dark food image - should return EMPTY_RESULT."""
    image_path = ASSETS_DIR / "blurry_food.jpg"
    if not image_path.exists():
        print(f"\nSKIP: {image_path} not found")
        return

    with open(image_path, "rb") as img:
        files = {"image": ("blurry.jpg", img, "image/jpeg")}
        data = {"locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        try:
            response = requests.post(
                API_URL, files=files, data=data, headers=headers, timeout=60
            )
        except Exception as e:
            print(f"\n❌ FAIL: Request failed: {e}")
            return

    print_result("Blurry Food Image", response)

    body = response.json()
    if check_auth_error(response.status_code, body):
        return

    # This might pass gate but fail recognition, or fail gate
    if body.get("error_code") in ["EMPTY_RESULT", "UNSUPPORTED_CONTENT"]:
        print(f"\n✅ PASS: Got {body.get('error_code')} (expected rejection)")
    elif body.get("status") == "success":
        print("\n⚠️  WARN: Image passed - may need a blurrier test image")
    else:
        print(f"\n? Got: {body.get('error_code', body.get('status'))}")


def test_unsupported_format():
    """Test with unsupported file format - should return UNSUPPORTED_IMAGE_FORMAT."""
    # Send a text file as image
    files = {"image": ("test.txt", b"this is not an image", "text/plain")}
    data = {"locale": "ru"}
    headers = {"X-API-Key": API_KEY}

    try:
        response = requests.post(
            API_URL, files=files, data=data, headers=headers, timeout=60
        )
    except Exception as e:
        print(f"\n❌ FAIL: Request failed: {e}")
        return

    print_result("Unsupported Format", response)

    body = response.json()
    if body.get("error_code") == "UNSUPPORTED_IMAGE_FORMAT":
        print("\n✅ PASS: Got UNSUPPORTED_IMAGE_FORMAT as expected")
    else:
        print(
            f"\n❌ FAIL: Expected UNSUPPORTED_IMAGE_FORMAT, got {body.get('error_code')}"
        )


def test_trace_id_propagation():
    """Test that trace_id is properly propagated."""
    custom_trace_id = "test-trace-12345678"

    image_path = ASSETS_DIR / "test_food_image.jpg"
    if not image_path.exists():
        print(f"SKIP: {image_path} not found")
        return

    with open(image_path, "rb") as img:
        files = {"image": ("test.jpg", img, "image/jpeg")}
        data = {"locale": "ru"}
        headers = {
            "X-API-Key": API_KEY,
            "X-Trace-Id": custom_trace_id,
        }

        try:
            response = requests.post(
                API_URL, files=files, data=data, headers=headers, timeout=60
            )
        except Exception as e:
            print(f"\n❌ FAIL: Request failed: {e}")
            return

    print_result("Trace ID Propagation", response)

    # Check trace_id in response
    body = response.json()
    response_trace_id = body.get("trace_id")
    header_trace_id = response.headers.get("X-Trace-Id")

    if response_trace_id == custom_trace_id and header_trace_id == custom_trace_id:
        print(f"\n✅ PASS: Trace ID correctly propagated: {custom_trace_id}")
    else:
        print(f"\n❌ FAIL: Trace ID mismatch")
        print(f"   Sent: {custom_trace_id}")
        print(f"   Body: {response_trace_id}")
        print(f"   Header: {header_trace_id}")


def main():
    if not API_KEY:
        print("ERROR: Set TEST_API_KEY or API_PROXY_SECRET environment variable")
        # print("Example: $env:TEST_API_KEY='your-secret-key'") # Powershell specific comment removed
        sys.exit(1)

    print("=" * 60)
    print("ANTI-HALLUCINATION GATE - INTEGRATION TESTS")
    print("=" * 60)
    print(f"Server: {API_URL}")
    print(f"Assets: {ASSETS_DIR}")

    try:
        test_normal_food()
        test_not_food()
        test_blurry_food()
        test_unsupported_format()
        test_trace_id_propagation()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to {API_URL}")
        print("   Make sure the server is running: uvicorn app.main:app --port 8001")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
