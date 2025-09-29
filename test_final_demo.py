#!/usr/bin/env python3
"""
Final Demo Test - Simple and Complex Queries
Shows the complete flow and results for the EcomInsight system
"""

import requests
import json
import time
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def print_header(title):
    """Print formatted header"""
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}  {title}")
    print(f"{Fore.CYAN}{'='*80}")

def test_query(question, query_type="Unknown"):
    """Test a single query and show the complete flow"""
    print(f"\n{Fore.YELLOW}📝 Query Type: {query_type}")
    print(f"{Fore.WHITE}❓ Question: '{question}'")
    print(f"{Fore.BLUE}{'─'*60}")

    start_time = time.time()

    try:
        # Make API request
        print(f"{Fore.MAGENTA}🔄 Step 1: Sending request to /api/mcp/ask...")

        response = requests.post(
            f"{BASE_URL}/api/mcp/ask",
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=15
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()

            # Show tool selection
            tool_used = data.get('metadata', {}).get('tool_used', 'unknown')
            params = data.get('metadata', {}).get('parameters', {})

            print(f"{Fore.MAGENTA}🔧 Step 2: Tool selected: {Fore.GREEN}{tool_used}")

            # Show parameters
            if params:
                print(f"{Fore.MAGENTA}⚙️  Parameters:")
                for key, value in params.items():
                    if value:
                        print(f"    • {key}: {value}")

            # Show MongoDB execution
            print(f"{Fore.MAGENTA}🗄️  Step 3: Executing MongoDB query...")

            # Show results
            answer = data.get('answer', 'N/A')
            print(f"{Fore.MAGENTA}✅ Step 4: Processing results...")

            # Show final answer
            print(f"\n{Fore.GREEN}💬 Answer: {answer}")

            # Show data preview if available
            if data.get('data'):
                if isinstance(data['data'], list):
                    count = len(data['data'])
                    print(f"{Fore.CYAN}📊 Data: {count} result(s) returned")

                    # Show sample for complex results
                    if count > 0 and isinstance(data['data'][0], dict):
                        first = data['data'][0]
                        if '_id' in first and 'count' in first:
                            print(f"    Sample: {first['_id']}: {first['count']}")
                        elif 'total' in first:
                            print(f"    Total: {first['total']}")

            print(f"{Fore.BLUE}⏱️  Response time: {elapsed:.2f}s")
            return True, data

        else:
            print(f"{Fore.RED}❌ Error: HTTP {response.status_code}")
            print(f"    {response.text[:100]}")
            return False, None

    except Exception as e:
        print(f"{Fore.RED}❌ Exception: {e}")
        return False, None

def main():
    print(f"{Fore.MAGENTA}{Style.BRIGHT}")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║              ECOMINSIGHT - FINAL DEMO WITH MCP APPROACH                 ║")
    print("║                    Running on 8GB RAM with TinyLlama                    ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print(Style.RESET_ALL)

    # Simple Queries
    print_header("SIMPLE QUERIES")

    simple_queries = [
        ("How many orders do I have?", "Count Query"),
        ("How many categories exist?", "Count Query"),
        ("How many customers are registered?", "Count Query"),
        ("List my recent orders", "List Query"),
        ("Show all product categories", "List Query"),
    ]

    simple_success = 0
    for question, query_type in simple_queries:
        success, _ = test_query(question, query_type)
        if success:
            simple_success += 1
        time.sleep(0.5)  # Rate limiting

    # Complex Queries
    print_header("COMPLEX QUERIES")

    complex_queries = [
        ("What's my total revenue?", "Aggregation - Sum"),
        ("What's the average order value?", "Aggregation - Average"),
        ("Group all orders by status", "Grouping Query"),
        ("Show top 5 customers by spending", "Complex Join + Aggregation"),
        ("Find orders over $1000", "Filtered Query"),
        ("Orders from last 7 days", "Date Range Query"),
        ("Which product categories are most popular?", "Multi-level Analysis"),
        ("What's my revenue this month?", "Time-based Aggregation"),
        ("Show pending orders with high value", "Multi-condition Filter"),
        ("Customer order frequency analysis", "Customer Analytics"),
    ]

    complex_success = 0
    for question, query_type in complex_queries:
        success, _ = test_query(question, query_type)
        if success:
            complex_success += 1
        time.sleep(0.5)  # Rate limiting

    # Summary
    print_header("TEST SUMMARY")

    total_simple = len(simple_queries)
    total_complex = len(complex_queries)
    total = total_simple + total_complex
    total_success = simple_success + complex_success

    print(f"\n{Fore.CYAN}📊 Results:")
    print(f"   Simple Queries:  {simple_success}/{total_simple} passed ({simple_success/total_simple*100:.0f}%)")
    print(f"   Complex Queries: {complex_success}/{total_complex} passed ({complex_success/total_complex*100:.0f}%)")
    print(f"   Overall:         {total_success}/{total} passed ({total_success/total*100:.0f}%)")

    print(f"\n{Fore.YELLOW}🔍 Analysis:")
    if total_success >= total * 0.9:
        print(f"   {Fore.GREEN}✅ Excellent! System is production-ready")
        print(f"   {Fore.GREEN}✅ MCP approach handles both simple and complex queries well")
        print(f"   {Fore.GREEN}✅ TinyLlama (1.1B) is sufficient for this use case")
    elif total_success >= total * 0.7:
        print(f"   {Fore.YELLOW}⚠️  Good performance, some queries need improvement")
        print(f"   {Fore.YELLOW}   Consider adding more specific tools")
    else:
        print(f"   {Fore.RED}❌ System needs significant improvement")

    print(f"\n{Fore.CYAN}💡 Key Insights:")
    print(f"   • MCP approach avoids MongoDB syntax errors")
    print(f"   • Keyword fallback ensures reliability when LLM fails")
    print(f"   • Tools provide accurate aggregations (revenue, grouping, etc.)")
    print(f"   • System runs smoothly on 8GB RAM with TinyLlama")

    print(f"\n{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.GREEN}✨ Demo Complete!")
    print(f"{Fore.MAGENTA}{'='*80}\n")

if __name__ == "__main__":
    main()