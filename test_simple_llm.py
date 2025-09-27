#!/usr/bin/env python3
"""
Test simple LLM queries that should work
"""

import asyncio
import httpx

async def test_simple_queries():
    """Test simple queries that LLM should handle easily."""

    queries = [
        "Find all completed orders",
        "Show me orders where grand_total is greater than 100",
        "List customers whose first name is John",
        "Count orders with status pending",
        "Show me the first 5 orders"
    ]

    for question in queries:
        print(f"\n🧪 Testing: {question}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/ask",
                    json={
                        "shop_id": "10",
                        "question": question
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Success: {result['answer'][:100]}...")
                    print(f"   Time: {result['processing_time']:.2f}s")
                    print(f"   Type: {result['query_type']}")
                else:
                    print(f"❌ HTTP {response.status_code}")

        except Exception as e:
            print(f"❌ Error: {e}")

        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_simple_queries())