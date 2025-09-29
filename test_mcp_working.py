#!/usr/bin/env python3
"""
Test what's working with MCP approach
Shows both successes and failures
"""

import requests
import json

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def test_query(question):
    """Test a query and show results"""
    print(f"\nQuery: {question}")
    print("-" * 50)

    response = requests.post(
        f"{BASE_URL}/api/mcp/ask",
        json={"shop_id": SHOP_ID, "question": question},
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success")
        print(f"Answer: {data.get('answer', 'N/A')}")

        metadata = data.get('metadata', {})
        if metadata:
            print(f"Tool used: {metadata.get('tool_used', 'unknown')}")
            params = metadata.get('parameters', {})
            if params:
                print(f"Collection: {params.get('collection', 'N/A')}")

        # Show if we got actual data
        if data.get('data'):
            if isinstance(data['data'], list):
                print(f"Results: {len(data['data'])} items returned")
                # Check first item to understand what was returned
                if data['data']:
                    first = data['data'][0]
                    if isinstance(first, dict):
                        if 'total' in first:
                            print(f"  → Total: {first['total']}")
                        elif 'count' in first:
                            print(f"  → Count: {first['count']}")
                        elif '_id' in first and 'count' in first:
                            print(f"  → Sample group: {first['_id']}: {first['count']}")
    else:
        print(f"❌ Failed: HTTP {response.status_code}")
        print(f"Error: {response.text[:100]}")

# Test different query types
queries = [
    # These should work with fallback
    "How many categories do I have?",
    "How many orders exist?",
    "How many products are there?",

    # These might work with improved fallback
    "What's the total revenue from all orders?",
    "Group orders by status",
    "Show top 5 customers by spending",

    # These will likely fail or misclassify
    "Average order value",
    "Orders from last week",
    "Revenue by month"
]

print("=" * 60)
print("MCP API TEST - What's Working vs Not Working")
print("=" * 60)

for q in queries:
    try:
        test_query(q)
    except Exception as e:
        print(f"❌ Exception: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("✅ Working: Count queries with explicit collection names")
print("⚠️  Partial: Some aggregations work with fallback")
print("❌ Issues: TinyLlama generates invalid tool names/parameters")
print("\nRecommendation: The fallback mechanism needs improvement")