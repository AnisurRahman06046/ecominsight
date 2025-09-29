#!/usr/bin/env python3
"""
Simple MCP Test
Quick test to see if MCP approach works
"""

import requests
import json

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def test_query(endpoint: str, question: str):
    """Test a query on given endpoint"""
    print(f"\nTesting: {question}")
    print(f"Endpoint: {endpoint}")
    print("-" * 50)

    try:
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"Answer: {data.get('answer', 'N/A')}")

            # Show metadata for MCP
            if '/mcp/' in endpoint and data.get('metadata'):
                print(f"Tool used: {data['metadata'].get('tool_used', 'unknown')}")
                params = data['metadata'].get('parameters', {})
                print(f"Collection: {params.get('collection', 'N/A')}")

            # Show pipeline for regular
            elif data.get('metadata', {}).get('generated_pipeline'):
                pipeline = data['metadata']['generated_pipeline']
                print(f"Pipeline stages: {len(pipeline)}")
                for stage in pipeline[:2]:
                    print(f"  {list(stage.keys())}")

            return True
        else:
            print(f"❌ Failed - HTTP {response.status_code}")
            print(f"Error: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTING MCP vs TRADITIONAL APPROACH")
    print("=" * 60)

    test_cases = [
        "How many categories do I have?",
        "Show me orders over $1000",
        "What's my total revenue?",
        "Group orders by status",
        "Top 5 customers by spending",
    ]

    for question in test_cases:
        print("\n" + "=" * 60)

        # Test traditional
        print("\n1. Traditional Approach (/api/ask):")
        test_query("/api/ask", question)

        # Test MCP
        print("\n2. MCP Approach (/api/mcp/ask):")
        test_query("/api/mcp/ask", question)

    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    main()