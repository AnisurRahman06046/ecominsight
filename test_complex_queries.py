#!/usr/bin/env python3
"""
Test Complex Natural Language Queries
Tests the LLM's ability to understand and process complex user queries
"""

import requests
import json
from colorama import Fore, init

init(autoreset=True)

BASE_URL = "http://localhost:8000/api/ask"
SHOP_ID = "10"

def test_query(description, question):
    """Test a single complex query"""
    print(f"\n{Fore.YELLOW}{'='*70}")
    print(f"{Fore.CYAN}Test: {description}")
    print(f"{Fore.BLUE}Query: {question}")
    print(f"{Fore.YELLOW}{'='*70}")

    try:
        response = requests.post(
            BASE_URL,
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            print(f"{Fore.GREEN}✅ Success")
            print(f"Answer: {data.get('answer', 'N/A')[:150]}...")
            print(f"Query Type: {data.get('query_type')}")
            print(f"Collection: {data.get('metadata', {}).get('collection')}")

            # Show pipeline
            pipeline = data.get('metadata', {}).get('generated_pipeline', [])
            if pipeline:
                print(f"\n{Fore.MAGENTA}Generated Pipeline:")
                for stage in pipeline[:3]:  # Show first 3 stages
                    print(f"  {json.dumps(stage, indent=2)[:100]}...")

            # Show sample data
            result_data = data.get('data', [])
            if result_data and isinstance(result_data, list):
                print(f"\n{Fore.CYAN}Sample Results ({len(result_data)} total):")
                for item in result_data[:2]:  # Show first 2 results
                    if isinstance(item, dict):
                        # Show key fields
                        preview = {}
                        for key in ['_id', 'total', 'count', 'name', 'grand_total', 'status']:
                            if key in item:
                                preview[key] = item[key]
                        if preview:
                            print(f"  {preview}")

            return True
        else:
            print(f"{Fore.RED}❌ Failed - HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"{Fore.RED}❌ Error: {e}")
        return False

def main():
    print(f"{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}TESTING COMPLEX NATURAL LANGUAGE QUERIES")
    print(f"{Fore.MAGENTA}Using LLM with full schema context")
    print(f"{Fore.MAGENTA}{'='*70}")

    # Define complex test queries
    test_cases = [
        # Basic Complex Queries
        ("Count with specific collection",
         "How many categories exist in my store?"),

        ("Filtering with conditions",
         "Show me orders with grand total more than 5000"),

        ("Sorting and limiting",
         "Give me the top 10 most expensive orders"),

        # Aggregation Queries
        ("Customer spending analysis",
         "Which customers have spent the most money in total?"),

        ("Product popularity",
         "What are my best selling products?"),

        ("Revenue calculation",
         "Calculate my total revenue from all orders"),

        # Time-based Queries
        ("Recent activity",
         "Show me orders from the last 7 days"),

        ("Monthly analysis",
         "What's my revenue this month?"),

        # Multi-condition Queries
        ("Complex filtering",
         "Find pending orders with amount greater than 1000"),

        ("Status analysis",
         "How many orders are in each status?"),

        # Business Intelligence
        ("Customer insights",
         "Who are my most valuable customers?"),

        ("Category performance",
         "Which product categories generate the most revenue?"),

        # Natural Language Variations
        ("Casual query 1",
         "how much money did i make today"),

        ("Casual query 2",
         "do i have any big orders waiting"),

        ("Business question",
         "what's my average order size"),
    ]

    # Track results
    passed = 0
    failed = 0

    for description, query in test_cases:
        if test_query(description, query):
            passed += 1
        else:
            failed += 1

    # Summary
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}SUMMARY")
    print(f"{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.GREEN}Passed: {passed}")
    print(f"{Fore.RED}Failed: {failed}")
    print(f"Total: {len(test_cases)}")
    print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%")

    if passed > len(test_cases) * 0.7:
        print(f"\n{Fore.GREEN}✅ LLM is handling complex queries well!")
    elif passed > len(test_cases) * 0.5:
        print(f"\n{Fore.YELLOW}⚠️ LLM handles some complex queries but needs improvement")
    else:
        print(f"\n{Fore.RED}❌ LLM is struggling with complex queries")

if __name__ == "__main__":
    main()