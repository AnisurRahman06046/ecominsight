#!/usr/bin/env python3
"""
Debug what the LLM is actually generating
"""

import asyncio
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test_llm_generation():
    """Test LLM generation with our actual prompt."""

    system_prompt = """You are a MongoDB query expert assistant for an e-commerce database.

Database Collections (use these exact names):
- order: {_id, id, shop_id, user_id, order_number, subtotal, grand_total, status, created_at}
- order_product: {_id, id, order_id, product_id, sku_id, name, price, quantity, total_price, status}
- product: {_id, id, shop_id, name, slug, category_id, brand_id, status, created_at}
- customer: {_id, id, shop_id, first_name, last_name, email, phone, status, created_at}
- sku: {_id, id, shop_id, product_id, price, stock_quantity, status, created_at}

IMPORTANT:
1. shop_id is stored as INTEGER (not string) - use integers in queries
2. Always start with $match for shop_id as integer
3. Use created_at for date fields
4. Return ONLY valid JSON, no explanations

EXAMPLE:
Question: "How many orders last week?"
Response:
{
  "pipeline": [{"$match": {"shop_id": 10}}, {"$count": "count"}],
  "collection": "order",
  "answer_template": "You had {count} orders last week"
}

For each query, return ONLY this JSON format:
{
  "pipeline": [...],
  "collection": "...",
  "answer_template": "..."
}"""

    user_prompt = """Shop ID: 10
Question: Show me orders from last week that have more than 3 items

Generate a MongoDB aggregation pipeline to answer this question."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral:7b-instruct",
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                    "format": "json",
                    "temperature": 0.1,
                },
            )

            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("response", "")

                print("🤖 LLM Generated:")
                print(generated_text)
                print("\n" + "="*50 + "\n")

                # Try to parse as JSON
                try:
                    parsed = json.loads(generated_text)
                    print("✅ Valid JSON structure:")
                    print(json.dumps(parsed, indent=2))

                    # Check pipeline validity
                    pipeline = parsed.get("pipeline", [])
                    print(f"\n🔍 Pipeline has {len(pipeline)} stages:")
                    for i, stage in enumerate(pipeline):
                        print(f"  {i+1}. {list(stage.keys())}")

                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
                    print("Raw response:")
                    print(repr(generated_text))

            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(response.text)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_generation())