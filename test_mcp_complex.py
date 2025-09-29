#!/usr/bin/env python3
"""
Test Complex Queries with MCP Approach
Compare how traditional vs MCP handles complex natural language queries
"""

import requests
import json
from colorama import Fore, init

init(autoreset=True)

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def test_query(endpoint: str, question: str, description: str):
    """Test a query and show detailed results"""
    print(f"\n{Fore.CYAN}Query: {question}")
    print(f"{Fore.YELLOW}Endpoint: {endpoint}")
    print("-" * 60)

    try:
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            print(f"{Fore.GREEN}✅ Success!")

            # Show answer
            answer = data.get('answer', 'N/A')
            print(f"{Fore.WHITE}Answer: {answer[:200]}")

            # For MCP, show tool used
            if '/mcp/' in endpoint and data.get('metadata'):
                tool = data['metadata'].get('tool_used', 'unknown')
                params = data['metadata'].get('parameters', {})
                print(f"{Fore.MAGENTA}Tool: {tool}")
                if params:
                    print(f"{Fore.MAGENTA}Parameters: {json.dumps(params, indent=2)[:100]}")

            # For traditional, show pipeline
            elif data.get('metadata', {}).get('generated_pipeline'):
                pipeline = data['metadata']['generated_pipeline']
                print(f"{Fore.BLUE}Pipeline: {json.dumps(pipeline, indent=2)[:200]}")

            # Show data preview
            if data.get('data'):
                if isinstance(data['data'], list):
                    print(f"{Fore.CYAN}Results: {len(data['data'])} items")
                    if len(data['data']) > 0:
                        # Show first result
                        first = data['data'][0]
                        if isinstance(first, dict):
                            # Extract key info
                            if 'total' in first:
                                print(f"  Total: {first['total']}")
                            if '_id' in first and 'count' in first:
                                print(f"  Sample: {first['_id']}: {first['count']}")
                            elif 'total_spent' in first:
                                print(f"  Top spender: ${first['total_spent']:,.2f}")

            return True, data
        else:
            print(f"{Fore.RED}❌ Failed - HTTP {response.status_code}")
            print(f"Error: {response.text[:200]}")
            return False, None

    except Exception as e:
        print(f"{Fore.RED}❌ Exception: {e}")
        return False, None

def compare_approaches(question: str, description: str):
    """Compare traditional vs MCP on same query"""
    print(f"\n{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}TEST: {description}")
    print(f"{Fore.MAGENTA}{'='*80}")

    # Test traditional
    print(f"\n{Fore.YELLOW}1. Traditional LLM Approach:")
    trad_success, trad_data = test_query("/api/ask", question, description)

    # Test MCP
    print(f"\n{Fore.YELLOW}2. MCP Tool-Based Approach:")
    mcp_success, mcp_data = test_query("/api/mcp/ask", question, description)

    # Compare results
    print(f"\n{Fore.YELLOW}Comparison:")
    if trad_success and mcp_success:
        trad_answer = trad_data.get('answer', 'N/A')
        mcp_answer = mcp_data.get('answer', 'N/A')

        # Extract numeric values for comparison
        import re

        trad_numbers = re.findall(r'[\d,]+\.?\d*', trad_answer)
        mcp_numbers = re.findall(r'[\d,]+\.?\d*', mcp_answer)

        print(f"Traditional numbers: {trad_numbers[:3]}")
        print(f"MCP numbers: {mcp_numbers[:3]}")

        if trad_answer != mcp_answer:
            print(f"{Fore.YELLOW}⚠️  Different results - MCP likely more accurate")
        else:
            print(f"{Fore.GREEN}✅ Same results")

    return trad_success, mcp_success

def main():
    print(f"{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}COMPLEX QUERY TESTING - MCP vs TRADITIONAL")
    print(f"{Fore.MAGENTA}{'='*80}")

    # Define complex test cases
    complex_queries = [
        # Aggregation queries
        ("What's the total revenue from all completed orders?",
         "Filtered aggregation"),

        ("Show me the average order value for each month",
         "Time-based grouping with calculation"),

        ("Which product categories generate the most revenue?",
         "Multi-collection join with aggregation"),

        # Complex filtering
        ("Find orders between $500 and $2000 that are pending",
         "Multiple filter conditions"),

        ("Show customers who have placed more than 5 orders",
         "Customer analysis with order count"),

        # Time-based queries
        ("What was my revenue last month?",
         "Date range with aggregation"),

        ("Show me today's orders",
         "Current date filtering"),

        # Top N with conditions
        ("Top 10 products by sales volume",
         "Product ranking"),

        ("Bottom 5 performing categories",
         "Reverse sorting"),

        # Business intelligence
        ("What's my conversion rate from pending to completed orders?",
         "Ratio calculation"),

        ("Which day of the week has the most orders?",
         "Day of week analysis"),

        ("What percentage of orders are above $1000?",
         "Percentage calculation"),

        # Natural language variations
        ("how much money did I make from electronics category",
         "Category-specific revenue"),

        ("do I have any big orders waiting to be processed",
         "Colloquial query with conditions"),

        ("what's the most popular product",
         "Popularity analysis"),
    ]

    # Track results
    trad_success = 0
    mcp_success = 0
    both_success = 0

    for query, description in complex_queries:
        trad_ok, mcp_ok = compare_approaches(query, description)
        if trad_ok:
            trad_success += 1
        if mcp_ok:
            mcp_success += 1
        if trad_ok and mcp_ok:
            both_success += 1

    # Summary
    print(f"\n{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}SUMMARY")
    print(f"{Fore.MAGENTA}{'='*80}")

    total = len(complex_queries)
    print(f"\nTotal queries tested: {total}")
    print(f"{Fore.CYAN}Traditional approach success: {trad_success}/{total} ({trad_success/total*100:.1f}%)")
    print(f"{Fore.GREEN}MCP approach success: {mcp_success}/{total} ({mcp_success/total*100:.1f}%)")
    print(f"Both succeeded: {both_success}/{total}")

    # Analysis
    print(f"\n{Fore.YELLOW}Analysis:")
    if mcp_success > trad_success:
        improvement = ((mcp_success - trad_success) / trad_success * 100) if trad_success > 0 else 100
        print(f"{Fore.GREEN}✅ MCP performs {improvement:.0f}% better than traditional approach")
    elif mcp_success == trad_success:
        print(f"{Fore.YELLOW}⚠️  MCP and traditional perform equally")
    else:
        print(f"{Fore.RED}❌ Traditional performs better than MCP")

    # Recommendations
    print(f"\n{Fore.CYAN}Recommendations:")
    if mcp_success >= total * 0.8:
        print(f"1. MCP approach is production-ready for most queries")
        print(f"2. Use MCP as primary, traditional as fallback")
    elif mcp_success >= total * 0.6:
        print(f"1. MCP works well but needs improvement for complex queries")
        print(f"2. Consider enhancing tool selection logic")
    else:
        print(f"1. MCP needs significant improvement")
        print(f"2. Add more tools for specific query patterns")
        print(f"3. Improve fallback mechanism")

if __name__ == "__main__":
    main()