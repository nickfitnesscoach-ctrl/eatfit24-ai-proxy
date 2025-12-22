"""Test the deployed AI API with different scenarios"""

import os
import sys
from pathlib import Path
import requests
import json

API_URL = os.environ.get(
    "TEST_API_URL", "http://localhost:8001/api/v1/ai/recognize-food"
)
API_KEY = os.environ.get("TEST_API_KEY") or os.environ.get("API_PROXY_SECRET")
IMAGE_PATH = Path(__file__).parent / "assets" / "test_food_image.jpg"

if not API_KEY:
    print("ERROR: Set TEST_API_KEY or API_PROXY_SECRET environment variable")
    print("Example: $env:TEST_API_KEY='your-secret-key'")
    sys.exit(1)


def test_scenario_1():
    """Test with explicit weights in comment"""
    print("\n" + "=" * 80)
    print("TEST 1: Comment with explicit weights")
    print("=" * 80)

    with open(IMAGE_PATH, "rb") as img:
        files = {"image": ("test.jpg", img, "image/jpeg")}
        data = {"user_comment": "Индейка 150 г, картофель 200 г", "locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        response = requests.post(
            API_URL, files=files, data=data, headers=headers, timeout=60
        )

        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            result = response.json()
            print(f"\n[SUCCESS]")
            print(f"Items found: {len(result['items'])}")
            for item in result["items"]:
                print(f"  - {item['name']}: {item['grams']}g (target: 150 or 200)")
        else:
            print(f"\n[FAILED] with status {response.status_code}")


def test_scenario_2():
    """Test without weights in comment"""
    print("\n" + "=" * 80)
    print("TEST 2: Comment without weights")
    print("=" * 80)

    with open(IMAGE_PATH, "rb") as img:
        files = {"image": ("test.jpg", img, "image/jpeg")}
        data = {"user_comment": "индейка и картофель", "locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        response = requests.post(
            API_URL, files=files, data=data, headers=headers, timeout=60
        )

        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            print(f"\n[SUCCESS]")
            print(f"Items found: {len(response.json()['items'])}")
        else:
            print(f"\n[FAILED] with status {response.status_code}")


def test_scenario_3():
    """Test with empty comment"""
    print("\n" + "=" * 80)
    print("TEST 3: Empty comment")
    print("=" * 80)

    with open(IMAGE_PATH, "rb") as img:
        files = {"image": ("test.jpg", img, "image/jpeg")}
        data = {"locale": "ru"}
        headers = {"X-API-Key": API_KEY}

        response = requests.post(
            API_URL, files=files, data=data, headers=headers, timeout=60
        )

        print(f"Status Code: {response.status_code}")
        print(f"\nResponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            print(f"\n[SUCCESS]")
            print(f"Items found: {len(response.json()['items'])}")
        else:
            print(f"\n[FAILED] with status {response.status_code}")


if __name__ == "__main__":
    print("TESTING AI PROXY API - WEIGHT PRIORITIZATION")
    print(f"Server: {API_URL}")
    print(f"Image: {IMAGE_PATH}")

    try:
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()

        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback

        traceback.print_exc()
