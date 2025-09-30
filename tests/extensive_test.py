#!/usr/bin/env python3
"""
Extensive Testing Script for MCP System
Tests 100 diverse queries and generates comprehensive report
"""

import requests
import json
import time
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

# 100 diverse test queries covering all scenarios
TEST_QUERIES = [
    # Basic Count Queries (10)
    ("How many orders do I have?", "BASIC_COUNT"),
    ("How many customers?", "BASIC_COUNT"),
    ("How many products?", "BASIC_COUNT"),
    ("Count all orders", "BASIC_COUNT"),
    ("Total number of customers", "BASIC_COUNT"),
    ("How many pending orders?", "BASIC_COUNT"),
    ("Count completed orders", "BASIC_COUNT"),
    ("How many delivered orders?", "BASIC_COUNT"),
    ("Number of canceled orders", "BASIC_COUNT"),
    ("How many confirmed orders?", "BASIC_COUNT"),

    # Sum Queries (10)
    ("What is my total revenue?", "SUM_QUERY"),
    ("Total sales", "SUM_QUERY"),
    ("Sum of all orders", "SUM_QUERY"),
    ("Total revenue from orders", "SUM_QUERY"),
    ("What is the total order value?", "SUM_QUERY"),
    ("Sum of delivery charges", "SUM_QUERY"),
    ("Total paid amount", "SUM_QUERY"),
    ("Revenue from paid orders", "SUM_QUERY"),
    ("Total revenue from pending orders", "SUM_QUERY"),
    ("Sum of completed orders", "SUM_QUERY"),

    # Average Queries (10)
    ("What is the average order value?", "AVERAGE_QUERY"),
    ("Average order amount", "AVERAGE_QUERY"),
    ("Mean order value", "AVERAGE_QUERY"),
    ("Average revenue per order", "AVERAGE_QUERY"),
    ("Average delivery charge", "AVERAGE_QUERY"),
    ("Average of paid orders", "AVERAGE_QUERY"),
    ("Mean value of pending orders", "AVERAGE_QUERY"),
    ("Average order value above $500", "AVERAGE_QUERY"),
    ("Average for completed orders", "AVERAGE_QUERY"),
    ("What is average order value for paid orders?", "AVERAGE_QUERY"),

    # Filtered Queries (15)
    ("Show me orders above $1000", "FILTER_AMOUNT"),
    ("Orders above $500", "FILTER_AMOUNT"),
    ("Find orders above $2000", "FILTER_AMOUNT"),
    ("Orders below $100", "FILTER_AMOUNT"),
    ("Show orders under $500", "FILTER_AMOUNT"),
    ("Orders between $500 and $2000", "FILTER_RANGE"),
    ("Orders between $1000 and $3000", "FILTER_RANGE"),
    ("Find orders between $100 and $500", "FILTER_RANGE"),
    ("Show paid orders", "FILTER_STATUS"),
    ("Find unpaid orders", "FILTER_STATUS"),
    ("Pending orders", "FILTER_STATUS"),
    ("Completed orders", "FILTER_STATUS"),
    ("Delivered orders", "FILTER_STATUS"),
    ("Canceled orders", "FILTER_STATUS"),
    ("Confirmed orders", "FILTER_STATUS"),

    # Multi-Filter Queries (10)
    ("Paid orders above $800", "MULTI_FILTER"),
    ("Pending orders above $1000", "MULTI_FILTER"),
    ("Completed orders above $500", "MULTI_FILTER"),
    ("Paid orders between $500 and $1500", "MULTI_FILTER"),
    ("Pending orders between $1000 and $2000", "MULTI_FILTER"),
    ("Unpaid orders above $1000", "MULTI_FILTER"),
    ("Delivered orders above $800", "MULTI_FILTER"),
    ("Confirmed orders above $500", "MULTI_FILTER"),
    ("Canceled orders above $100", "MULTI_FILTER"),
    ("Paid orders under $200", "MULTI_FILTER"),

    # Top N Queries (10)
    ("Show me top 5 customers", "TOP_N"),
    ("Top 10 customers", "TOP_N"),
    ("Top 3 customers by spending", "TOP_N"),
    ("Show me best customers", "TOP_N"),
    ("Top 5 orders", "TOP_N"),
    ("Highest spending customers", "TOP_N"),
    ("Top 10 orders by value", "TOP_N"),
    ("Best selling products", "TOP_N"),
    ("Top products", "TOP_N"),
    ("Top 5 customers by order count", "TOP_N"),

    # Grouping Queries (10)
    ("How many orders by status", "GROUPING"),
    ("Group orders by status", "GROUPING"),
    ("Orders grouped by payment status", "GROUPING"),
    ("Count orders by status", "GROUPING"),
    ("Breakdown by status", "GROUPING"),
    ("Orders by payment method", "GROUPING"),
    ("Group by order status", "GROUPING"),
    ("Show me order status breakdown", "GROUPING"),
    ("Count by order status", "GROUPING"),
    ("Distribution of orders by status", "GROUPING"),

    # Time-Based Queries (10)
    ("Orders from last 7 days", "TIME_RANGE"),
    ("Show me orders from last week", "TIME_RANGE"),
    ("Orders from last 30 days", "TIME_RANGE"),
    ("Orders from last month", "TIME_RANGE"),
    ("Today's orders", "TIME_RANGE"),
    ("Yesterday's orders", "TIME_RANGE"),
    ("Orders from 2024", "TIME_RANGE"),
    ("Orders from this year", "TIME_RANGE"),
    ("Recent orders", "TIME_RANGE"),
    ("Latest orders", "TIME_RANGE"),

    # Complex Aggregation (10)
    ("Average order value for paid orders above $800", "COMPLEX_AGG"),
    ("Total revenue from pending orders above $1000", "COMPLEX_AGG"),
    ("Average of completed orders above $500", "COMPLEX_AGG"),
    ("Sum of paid orders between $500 and $2000", "COMPLEX_AGG"),
    ("Average order value for last 30 days", "COMPLEX_AGG"),
    ("Total revenue from orders above $1000", "COMPLEX_AGG"),
    ("Average value of paid orders", "COMPLEX_AGG"),
    ("Total from pending orders above $500", "COMPLEX_AGG"),
    ("Average of orders between $1000 and $3000", "COMPLEX_AGG"),
    ("Sum of completed orders above $800", "COMPLEX_AGG"),

    # Comparison Queries (5)
    ("Compare pending vs completed orders", "COMPARISON"),
    ("Pending vs paid orders", "COMPARISON"),
    ("Compare paid and unpaid orders", "COMPARISON"),
    ("Difference between pending and delivered", "COMPARISON"),
    ("Compare order counts by status", "COMPARISON"),
]

results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "by_category": {},
    "details": [],
    "response_times": []
}

def test_query(question: str, category: str, index: int):
    """Test a single query"""
    print(f"\n{Fore.CYAN}[{index}/100] Testing: {question}")
    print(f"{Fore.YELLOW}Category: {category}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/api/mcp/ask",
            json={
                "shop_id": SHOP_ID,
                "question": question,
                "use_cache": False
            },
            timeout=90
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'N/A')
            metadata = data.get('metadata', {})

            # Determine if passed
            passed = (
                answer and
                answer != "N/A" and
                len(answer) > 10 and
                not answer.startswith("Error") and
                "failed" not in answer.lower()
            )

            status = f"{Fore.GREEN}✅ PASS" if passed else f"{Fore.RED}❌ FAIL"

            print(f"{status}")
            print(f"{Fore.WHITE}Answer: {answer[:120]}..." if len(answer) > 120 else f"{Fore.WHITE}Answer: {answer}")
            print(f"{Fore.MAGENTA}Tool: {metadata.get('tool_used', 'N/A')}")
            print(f"{Fore.MAGENTA}Time: {elapsed:.2f}s")

            # Store result
            result = {
                "index": index,
                "question": question,
                "category": category,
                "passed": passed,
                "answer": answer,
                "tool": metadata.get('tool_used', 'N/A'),
                "intent": metadata.get('intent', 'N/A'),
                "time": elapsed,
                "error": None
            }

            results["details"].append(result)
            results["total"] += 1
            results["response_times"].append(elapsed)

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            return passed

        else:
            print(f"{Fore.RED}❌ FAIL - HTTP {response.status_code}")

            results["details"].append({
                "index": index,
                "question": question,
                "category": category,
                "passed": False,
                "error": f"HTTP {response.status_code}"
            })
            results["total"] += 1
            results["failed"] += 1
            return False

    except Exception as e:
        print(f"{Fore.RED}❌ FAIL - Exception: {str(e)[:100]}")
        results["details"].append({
            "index": index,
            "question": question,
            "category": category,
            "passed": False,
            "error": str(e)[:200]
        })
        results["total"] += 1
        results["failed"] += 1
        return False

def print_summary():
    """Print test summary"""
    print(f"\n\n{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}EXTENSIVE TEST SUMMARY (100 QUERIES)")
    print(f"{Fore.MAGENTA}{'='*80}\n")

    total = results["total"]
    passed = results["passed"]
    failed = results["failed"]
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"{Fore.WHITE}Total Tests: {total}")
    print(f"{Fore.GREEN}Passed: {passed} ({pass_rate:.1f}%)")
    print(f"{Fore.RED}Failed: {failed} ({100-pass_rate:.1f}%)")

    # By category
    print(f"\n{Fore.CYAN}Results by Category:")
    categories = {}
    for detail in results["details"]:
        cat = detail["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if detail["passed"]:
            categories[cat]["passed"] += 1

    for cat, stats in sorted(categories.items()):
        cat_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        status_color = Fore.GREEN if cat_rate >= 80 else Fore.YELLOW if cat_rate >= 60 else Fore.RED
        print(f"{status_color}{cat}: {stats['passed']}/{stats['total']} ({cat_rate:.0f}%)")

    # Response times
    if results["response_times"]:
        avg_time = sum(results["response_times"]) / len(results["response_times"])
        min_time = min(results["response_times"])
        max_time = max(results["response_times"])
        print(f"\n{Fore.CYAN}Response Time Statistics:")
        print(f"{Fore.WHITE}Average: {avg_time:.2f}s")
        print(f"{Fore.WHITE}Min: {min_time:.2f}s")
        print(f"{Fore.WHITE}Max: {max_time:.2f}s")

    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"extensive_test_report_{timestamp}.json"

    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{Fore.GREEN}Detailed report saved to: {report_file}")

def main():
    print(f"{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}EXTENSIVE MCP SYSTEM TESTING - 100 QUERIES")
    print(f"{Fore.MAGENTA}{'='*80}\n")
    print(f"{Fore.YELLOW}Testing diverse queries step by step...\\n")

    # Run all tests
    for index, (question, category) in enumerate(TEST_QUERIES, 1):
        test_query(question, category, index)
        time.sleep(0.3)  # Small delay between tests

    # Print final summary
    print_summary()

if __name__ == "__main__":
    main()