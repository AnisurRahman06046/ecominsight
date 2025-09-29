#!/usr/bin/env python3
"""
Test MongoDB MCP Approach
Tests the tool-based approach vs raw query generation
"""

import requests
import json
from colorama import Fore, init

init(autoreset=True)

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def test_mcp_query(description: str, question: str):
    """Test a single query using MCP approach"""
    print(f"\n{Fore.YELLOW}{'='*70}")
    print(f"{Fore.CYAN}Test: {description}")
    print(f"{Fore.BLUE}Query: {question}")
    print(f"{Fore.YELLOW}{'='*70}")

    try:
        # Test MCP endpoint
        response = requests.post(
            f"{BASE_URL}/api/mcp/ask",
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=30
        )

        if response.status_code == 200:
                data = response.json()
                print(f"{Fore.GREEN}✅ MCP Success")
                print(f"Answer: {data.get('answer', 'N/A')}")

                if data.get('metadata'):
                    tool_used = data['metadata'].get('tool_used')
                    params = data['metadata'].get('parameters', {})
                    print(f"\n{Fore.MAGENTA}Tool Used: {tool_used}")
                    print(f"Parameters: {json.dumps(params, indent=2)[:200]}")

                if data.get('data'):
                    print(f"\n{Fore.CYAN}Result Count: {len(data['data']) if isinstance(data['data'], list) else 1}")
                    if isinstance(data['data'], list) and len(data['data']) > 0:
                        print(f"Sample: {json.dumps(data['data'][0], indent=2)[:200]}...")

                return True
            else:
                print(f"{Fore.RED}❌ MCP Failed - HTTP {response.status_code}")
                print(f"Error: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")
            return False

async def compare_approaches(description: str, question: str):
    """Compare MCP vs traditional approach"""
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}Comparison: {description}")
    print(f"{Fore.MAGENTA}{'='*70}")

    async with httpx.AsyncClient(timeout=30) as client:
        # Test traditional approach
        print(f"\n{Fore.YELLOW}1. Traditional LLM Query Generation:")
        try:
            response = await client.post(
                f"{BASE_URL}/api/ask",
                json={
                    "shop_id": SHOP_ID,
                    "question": question,
                    "use_cache": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                pipeline = data.get('metadata', {}).get('generated_pipeline', [])
                print(f"{Fore.GREEN}✅ Success")
                print(f"Pipeline: {json.dumps(pipeline, indent=2)[:300]}")
            else:
                print(f"{Fore.RED}❌ Failed")
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")

        # Test MCP approach
        print(f"\n{Fore.YELLOW}2. MCP Tool-Based Approach:")
        try:
            response = await client.post(
                f"{BASE_URL}/api/mcp/ask",
                json={
                    "shop_id": SHOP_ID,
                    "question": question,
                    "use_cache": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                tool_used = data.get('metadata', {}).get('tool_used')
                print(f"{Fore.GREEN}✅ Success")
                print(f"Tool: {tool_used}")
                print(f"Answer: {data.get('answer', 'N/A')[:100]}")
            else:
                print(f"{Fore.RED}❌ Failed: {response.text[:100]}")
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}")

async def main():
    print(f"{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}MONGODB MCP APPROACH TESTING")
    print(f"{Fore.MAGENTA}Testing tool-based vs query generation approach")
    print(f"{Fore.MAGENTA}{'='*70}")

    # Test cases
    test_cases = [
        ("Simple count", "How many categories do I have?"),
        ("Filtered search", "Show me orders over $1000"),
        ("Aggregation", "What's my total revenue?"),
        ("Grouping", "Group orders by status"),
        ("Top N", "Show top 5 customers by spending"),
        ("Date range", "Orders from last 7 days"),
        ("Average calculation", "What's the average order value?"),
    ]

    # First test if MCP is working at all
    print(f"\n{Fore.CYAN}Testing MCP endpoint...")
    success_count = 0
    failed_count = 0

    for description, query in test_cases:
        if await test_mcp_query(description, query):
            success_count += 1
        else:
            failed_count += 1
        await asyncio.sleep(1)  # Rate limiting

    # Summary
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}SUMMARY")
    print(f"{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.GREEN}Successful: {success_count}")
    print(f"{Fore.RED}Failed: {failed_count}")
    print(f"Success Rate: {(success_count/(success_count+failed_count)*100):.1f}%")

    if success_count > len(test_cases) * 0.7:
        print(f"\n{Fore.GREEN}✅ MCP approach is working well!")
    elif success_count > len(test_cases) * 0.5:
        print(f"\n{Fore.YELLOW}⚠️ MCP approach works but needs improvement")
    else:
        print(f"\n{Fore.RED}❌ MCP approach is not working properly")

    # Compare approaches for a few queries
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}DETAILED COMPARISON")
    print(f"{Fore.MAGENTA}{'='*70}")

    comparison_cases = [
        ("Count Query", "How many products do I have?"),
        ("Complex Aggregation", "Show top customers by total spending"),
    ]

    for description, query in comparison_cases:
        await compare_approaches(description, query)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())