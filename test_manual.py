#!/usr/bin/env python3
"""
Interactive API Testing for EcomInsight
Allows manual testing of different query types
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_query(endpoint, shop_id, question):
    """Send a query to the API and display results"""
    url = f"{BASE_URL}{endpoint}"
    payload = {
        "shop_id": shop_id,
        "question": question,
        "use_cache": False
    }

    print(f"\n🔄 Sending to {endpoint}...")
    print(f"📝 Query: {question}")
    print("-" * 60)

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        print(f"✅ Answer: {result.get('answer', 'No answer')}")
        print(f"⚡ Type: {result.get('query_type', 'unknown')}")
        print(f"⏱️  Time: {result.get('processing_time', 0):.2f}s")

        if result.get('data'):
            print(f"\n📊 Data Preview:")
            data_str = json.dumps(result['data'], indent=2)
            print(data_str[:500] + ("..." if len(data_str) > 500 else ""))

        if result.get('metadata'):
            print(f"\n📋 Metadata:")
            meta_str = json.dumps(result['metadata'], indent=2)
            print(meta_str[:500] + ("..." if len(meta_str) > 500 else ""))

        return result

    except requests.exceptions.Timeout:
        print("❌ Request timed out (60s)")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json()
                print(f"Details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Response: {e.response.text[:500]}")

    return None

def main():
    print("🚀 EcomInsight Interactive API Tester")
    print("="*60)
    print("\nEndpoints:")
    print("1. /api/ask     - LLM-generated queries (complex)")
    print("2. /api/ask-v2  - Template-based queries (fast)")
    print("3. /api/ask-v3  - Hybrid approach")
    print("q. Quit")
    print("\n" + "="*60)

    # Default shop ID
    shop_id = input("\n🏪 Enter Shop ID (default: 1): ").strip() or "1"

    while True:
        print("\n" + "-"*60)
        endpoint_choice = input("\n📍 Choose endpoint (1/2/3/q): ").strip()

        if endpoint_choice.lower() == 'q':
            print("\n👋 Goodbye!")
            break

        endpoint_map = {
            '1': '/api/ask',
            '2': '/api/ask-v2',
            '3': '/api/ask-v3'
        }

        endpoint = endpoint_map.get(endpoint_choice)
        if not endpoint:
            print("❌ Invalid choice. Try again.")
            continue

        question = input("❓ Enter your query: ").strip()
        if not question:
            print("❌ Query cannot be empty.")
            continue

        test_query(endpoint, shop_id, question)

if __name__ == "__main__":
    main()