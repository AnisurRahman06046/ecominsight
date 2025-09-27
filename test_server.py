#!/usr/bin/env python3
"""
Test script for Ecommerce Insights Server
Tests all three paths: KPI, LLM, and RAG
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Test configuration
TEST_SHOP_ID = "123"  # You may need to adjust based on your data

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_result(test_name: str, success: bool, response_time: float, details: str = ""):
    """Pretty print test results."""
    status = f"{GREEN}✅ PASS{RESET}" if success else f"{RED}❌ FAIL{RESET}"
    print(f"\n{status} {test_name}")
    print(f"   ⏱️  Response time: {response_time:.3f}s")
    if details:
        print(f"   📝 {details}")


async def test_health():
    """Test health endpoint."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get(f"{BASE_URL}/health")
        elapsed = time.time() - start

        success = response.status_code == 200
        data = response.json()

        print_result(
            "Health Check",
            success,
            elapsed,
            f"Status: {data.get('status', 'unknown')}"
        )

        if data.get("services"):
            print(f"   Services:")
            for service, status in data["services"].items():
                emoji = "✅" if status else "❌"
                print(f"     {emoji} {service}: {status}")

        return success


async def test_kpi_query(question: str, expected_type: str = "kpi"):
    """Test KPI query (should be fast)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        start = time.time()

        payload = {
            "shop_id": TEST_SHOP_ID,
            "question": question
        }

        try:
            response = await client.post(
                f"{BASE_URL}/api/ask",
                json=payload
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                success = data.get("query_type") == expected_type

                print_result(
                    f"KPI Query: {question[:50]}...",
                    success,
                    elapsed,
                    f"Answer: {data.get('answer', 'No answer')[:100]}..."
                )

                # Check if it was cached
                if data.get("cached"):
                    print(f"   💾 Result was cached")

                # Show query type
                print(f"   🔍 Query type: {data.get('query_type', 'unknown')}")

                return success
            else:
                print_result(
                    f"KPI Query: {question[:50]}...",
                    False,
                    elapsed,
                    f"HTTP {response.status_code}: {response.text[:100]}"
                )
                return False

        except httpx.TimeoutException:
            elapsed = time.time() - start
            print_result(
                f"KPI Query: {question[:50]}...",
                False,
                elapsed,
                "Request timed out"
            )
            return False
        except Exception as e:
            elapsed = time.time() - start
            print_result(
                f"KPI Query: {question[:50]}...",
                False,
                elapsed,
                f"Error: {str(e)}"
            )
            return False


async def test_all_queries():
    """Test various query types."""
    print(f"\n{BLUE}═══════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}     ECOMMERCE INSIGHTS SERVER TEST SUITE{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════{RESET}")

    # Track results
    results = []

    # 1. Test health
    print(f"\n{YELLOW}1. Testing Health Endpoint...{RESET}")
    results.append(await test_health())

    # 2. Test KPI queries (should be fast <1s)
    print(f"\n{YELLOW}2. Testing KPI Queries (Fast Path)...{RESET}")

    kpi_queries = [
        "How many orders do I have?",
        "What's my total revenue today?",
        "Show me top 5 customers",
        "How many active products do I have?",
        "What products are low in stock?",
        "What's my average order value this month?",
    ]

    for query in kpi_queries:
        results.append(await test_kpi_query(query, "kpi"))
        await asyncio.sleep(0.5)  # Small delay between requests

    # 3. Test the same query twice (should be cached)
    print(f"\n{YELLOW}3. Testing Cache (Second query should be instant)...{RESET}")

    cache_query = "How many products did I sell yesterday?"
    print(f"   First query:")
    results.append(await test_kpi_query(cache_query, "kpi"))

    print(f"   Second query (should be cached):")
    results.append(await test_kpi_query(cache_query, "kpi"))

    # 4. Test complex queries (LLM path)
    print(f"\n{YELLOW}4. Testing Complex Queries (LLM Path)...{RESET}")

    complex_queries = [
        "Find orders with more than 3 items",
        "Show me customers who ordered in the last 7 days",
        "What's the total revenue from electronics category?",
    ]

    for query in complex_queries:
        results.append(await test_kpi_query(query, "unknown"))
        await asyncio.sleep(0.5)

    # 5. Test analytical queries (RAG path)
    print(f"\n{YELLOW}5. Testing Analytical Queries (RAG Path)...{RESET}")

    analytical_queries = [
        "Why did sales drop last month?",
        "How can I improve customer retention?",
        "What factors affect my conversion rate?",
    ]

    for query in analytical_queries:
        results.append(await test_kpi_query(query, "analytical"))
        await asyncio.sleep(0.5)

    # Summary
    print(f"\n{BLUE}═══════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}                    TEST SUMMARY{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════{RESET}")

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\n   Total Tests: {total}")
    print(f"   {GREEN}Passed: {passed}{RESET}")
    print(f"   {RED}Failed: {failed}{RESET}")
    print(f"   Success Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print(f"\n{GREEN}🎉 All tests passed!{RESET}")
    else:
        print(f"\n{YELLOW}⚠️  Some tests failed. Check the logs above.{RESET}")


async def test_models():
    """Test available models."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/models")
        if response.status_code == 200:
            data = response.json()
            print(f"\n{BLUE}Available Ollama Models:{RESET}")
            for model in data.get("models", []):
                print(f"   • {model}")

            print(f"\n{BLUE}Configured Model:{RESET}")
            print(f"   • {data.get('current', 'Not set')}")


async def main():
    """Main test runner."""
    print("🚀 Starting Ecommerce Insights Server Tests")
    print(f"📍 Testing server at: {BASE_URL}")
    print(f"🏪 Using shop_id: {TEST_SHOP_ID}")

    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"{BASE_URL}/health", timeout=2.0)
    except:
        print(f"\n{RED}❌ Server is not running!{RESET}")
        print(f"   Start it with: cd ecom-insights-server && ./run.sh")
        return

    # Run tests
    await test_all_queries()

    # Show available models
    await test_models()

    print(f"\n✅ Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())