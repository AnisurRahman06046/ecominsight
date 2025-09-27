#!/usr/bin/env python3
"""
Test Ollama connection and model availability
"""

import httpx
import asyncio
import json

async def test_ollama():
    """Test Ollama service."""
    base_url = "http://localhost:11434"

    print("🔍 Testing Ollama connection...\n")

    # 1. Check if Ollama is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                print("✅ Ollama is running!")
                models = response.json().get("models", [])
                print(f"\n📦 Available models:")
                for model in models:
                    print(f"   - {model.get('name')} ({model.get('size', 0) / 1e9:.1f} GB)")
            else:
                print(f"❌ Ollama responded with status {response.status_code}")
                return
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("   Make sure Ollama is running: ollama serve")
        return

    # 2. Test model generation
    print("\n🧪 Testing model generation...")

    test_model = "mistral:7b-instruct"  # or whatever model you have

    # Check if we have the right model
    model_exists = any(test_model in m.get("name", "") for m in models)

    if not model_exists:
        print(f"⚠️  Model {test_model} not found!")
        if models:
            test_model = models[0]["name"]
            print(f"   Using {test_model} instead")
        else:
            print("❌ No models available! Pull one with: ollama pull mistral:7b-instruct")
            return

    # 3. Test generation
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"\n🤖 Testing generation with {test_model}...")

            payload = {
                "model": test_model,
                "prompt": "Generate a MongoDB aggregation pipeline to count documents. Return only valid JSON.",
                "stream": False,
                "temperature": 0.1
            }

            response = await client.post(
                f"{base_url}/api/generate",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Generation successful!")
                print(f"   Response preview: {result.get('response', '')[:200]}...")
            else:
                print(f"❌ Generation failed with status {response.status_code}")
                print(f"   Response: {response.text}")

    except httpx.TimeoutException:
        print("❌ Generation timed out! Model might be loading...")
        print("   Try again in a moment")
    except Exception as e:
        print(f"❌ Generation error: {e}")

    # 4. Test JSON format generation
    print("\n🧪 Testing JSON format generation...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": test_model,
                "prompt": """Return a JSON object with this exact structure:
{
  "pipeline": [{"$match": {"shop_id": 10}}, {"$count": "total"}],
  "collection": "orders",
  "answer_template": "Found {total} orders"
}

Only return the JSON, no explanation.""",
                "stream": False,
                "format": "json",
                "temperature": 0.1
            }

            response = await client.post(
                f"{base_url}/api/generate",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                generated = result.get('response', '')
                print("✅ JSON generation successful!")

                # Try to parse the JSON
                try:
                    parsed = json.loads(generated)
                    print(f"   Valid JSON generated: {list(parsed.keys())}")
                except json.JSONDecodeError as e:
                    print(f"⚠️  Generated text is not valid JSON: {e}")
                    print(f"   Generated: {generated[:200]}...")
            else:
                print(f"❌ JSON generation failed: {response.status_code}")

    except Exception as e:
        print(f"❌ JSON generation error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())