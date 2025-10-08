#!/usr/bin/env python3
"""
Comprehensive System Test Suite
Tests all capabilities of the EcomInsight system with diverse query types
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple

API_URL = "http://localhost:8000/api/mcp/ask"
SHOP_ID = "13"

# Comprehensive test queries covering all system capabilities
TEST_QUERIES = {
    "COUNT_QUERIES": [
        "How many products do I have?",
        "How many orders?",
        "How many customers?",
        "Count my products",
        "Total number of orders",
        "Customer count",
        "How many items in catalog?",
        "Number of sales",
    ],

    "REVENUE_QUERIES": [
        "What is my total sales?",
        "Total revenue?",
        "Show me revenue",
        "How much did I sell?",
        "What are my total sales?",
        "My revenue",
        "Give me total sales",
        "Sales amount",
    ],

    "DATE_BASED_QUERIES": [
        "What is yesterday's total sales?",
        "Yesterday's revenue?",
        "How much did I sell yesterday?",
        "Today's sales?",
        "This week sales?",
        "This month sales?",
        "Last week revenue?",
        "Last month revenue?",
        "Revenue from last 30 days?",
        "Sales from today",
        "How much today?",
    ],

    "TOP_PRODUCTS_QUERIES": [
        "What are my top products?",
        "Best selling products?",
        "Show me top sellers",
        "Top 5 products?",
        "Top 10 products",
        "Most popular products?",
        "Best products?",
        "What are my best sellers?",
        "Which products are selling most?",
    ],

    "TOP_CUSTOMERS_QUERIES": [
        "Who are my top customers?",
        "Best customers?",
        "Show me top spenders",
        "Top 5 customers?",
        "Top 10 customers",
        "Most valuable customers?",
        "Who spends the most?",
        "Show top customers",
        "Best buyers?",
    ],

    "AVERAGE_QUERIES": [
        "What's my average order value?",
        "Average order amount?",
        "Mean order value?",
        "Average sale per order?",
        "What is the average revenue per order?",
    ],

    "TIME_GROUPING_QUERIES_HIGH": [
        "Which month has the highest order?",
        "Which month has the most orders?",
        "Best performing month?",
        "Top month by orders?",
        "Which day has most orders?",
        "Highest sales month?",
    ],

    "TIME_GROUPING_QUERIES_LOW": [
        "Which month has the lowest order?",
        "Which month has fewest orders?",
        "Worst performing month?",
        "Bottom month by orders?",
        "Least orders month?",
        "Smallest sales month?",
    ],

    "BREAKDOWN_QUERIES": [
        "Orders by status",
        "Monthly order breakdown",
        "Show me breakdown by month",
        "Order distribution",
        "Sales by month",
        "Payment status breakdown",
        "Order count by month",
    ],

    "STATUS_QUERIES": [
        "How many pending orders?",
        "How many completed orders?",
        "How many cancelled orders?",
        "Orders by status",
        "Show me pending orders count",
    ],

    "COMPLEX_QUERIES": [
        "How many orders did I get this month?",
        "How many new customers this month?",
        "Orders placed last 7 days?",
        "How many orders today?",
        "Products sold today?",
        "Customer growth this month?",
    ],

    "EDGE_CASES": [
        "Hello",  # Conversational
        "Help me",  # Conversational
        "My sales",  # Ambiguous
        "Revenue",  # Single word
        "what is the total sales of yestarday?",  # Typo
        "Total",  # Very ambiguous
    ],
}

def run_query(question: str) -> Tuple[bool, Dict, float]:
    """
    Run a single query and return success status, response, and time taken.
    """
    start_time = time.time()

    try:
        response = requests.post(
            API_URL,
            json={"shop_id": SHOP_ID, "question": question},
            timeout=60
        )
        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            return True, data, elapsed_time
        else:
            return False, {"error": f"HTTP {response.status_code}"}, elapsed_time

    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        return False, {"error": "Timeout (>60s)"}, elapsed_time
    except Exception as e:
        elapsed_time = time.time() - start_time
        return False, {"error": str(e)}, elapsed_time

def run_comprehensive_test():
    """
    Run all test queries and generate comprehensive report.
    """
    print("=" * 80)
    print("COMPREHENSIVE SYSTEM TEST")
    print("=" * 80)
    print(f"API: {API_URL}")
    print(f"Shop ID: {SHOP_ID}")
    print(f"Started: {datetime.now()}")
    print("=" * 80)
    print()

    # Statistics
    total_queries = 0
    successful_queries = 0
    failed_queries = 0
    total_time = 0.0

    category_stats = {}
    all_results = []

    # Run tests by category
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'=' * 80}")
        print(f"CATEGORY: {category}")
        print(f"{'=' * 80}\n")

        category_success = 0
        category_total = len(queries)
        category_time = 0.0

        for idx, query in enumerate(queries, 1):
            total_queries += 1

            print(f"[{idx}/{category_total}] Testing: {query}")

            success, response, elapsed = run_query(query)

            total_time += elapsed
            category_time += elapsed

            if success:
                successful_queries += 1
                category_success += 1
                answer = response.get("answer", "NO ANSWER")
                # Truncate long answers
                if len(answer) > 100:
                    answer = answer[:100] + "..."
                print(f"  ✓ SUCCESS ({elapsed:.2f}s)")
                print(f"  Answer: {answer}")

                # Store metadata
                metadata = response.get("metadata", {})
                tool_used = metadata.get("tool_used", "unknown")
                confidence = metadata.get("confidence", 0.0)
                routing = metadata.get("routing_method", "unknown")

                print(f"  Tool: {tool_used} | Confidence: {confidence:.3f} | Routing: {routing}")

                all_results.append({
                    "category": category,
                    "query": query,
                    "success": True,
                    "answer": response.get("answer"),
                    "tool_used": tool_used,
                    "confidence": confidence,
                    "routing_method": routing,
                    "response_time": elapsed
                })

            else:
                failed_queries += 1
                error = response.get("error", "Unknown error")
                print(f"  ✗ FAILED ({elapsed:.2f}s)")
                print(f"  Error: {error}")

                all_results.append({
                    "category": category,
                    "query": query,
                    "success": False,
                    "error": error,
                    "response_time": elapsed
                })

            print()

        # Category summary
        success_rate = (category_success / category_total * 100) if category_total > 0 else 0
        avg_time = category_time / category_total if category_total > 0 else 0

        category_stats[category] = {
            "total": category_total,
            "successful": category_success,
            "failed": category_total - category_success,
            "success_rate": success_rate,
            "avg_time": avg_time
        }

        print(f"Category Summary: {category_success}/{category_total} successful ({success_rate:.1f}%)")
        print(f"Average time: {avg_time:.2f}s")

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    print(f"Total Queries:    {total_queries}")
    print(f"Successful:       {successful_queries} ({successful_queries/total_queries*100:.1f}%)")
    print(f"Failed:           {failed_queries} ({failed_queries/total_queries*100:.1f}%)")
    print(f"Avg Response:     {total_time/total_queries:.2f}s")
    print(f"Total Time:       {total_time:.2f}s")
    print("=" * 80)

    # Category breakdown
    print("\nCATEGORY BREAKDOWN:")
    print("-" * 80)
    print(f"{'Category':<35} {'Success Rate':<15} {'Avg Time':<15}")
    print("-" * 80)

    for category, stats in category_stats.items():
        print(f"{category:<35} {stats['successful']}/{stats['total']} ({stats['success_rate']:.1f}%)     {stats['avg_time']:.2f}s")

    print("=" * 80)

    # Tool usage distribution
    tool_usage = {}
    routing_usage = {"semantic": 0, "llm_fallback": 0, "conversational": 0, "unknown": 0}

    for result in all_results:
        if result["success"]:
            tool = result.get("tool_used", "unknown")
            tool_usage[tool] = tool_usage.get(tool, 0) + 1

            routing = result.get("routing_method", "unknown")
            routing_usage[routing] = routing_usage.get(routing, 0) + 1

    print("\nTOOL USAGE DISTRIBUTION:")
    print("-" * 80)
    for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
        percentage = count / successful_queries * 100 if successful_queries > 0 else 0
        print(f"{tool:<35} {count:>5} ({percentage:.1f}%)")

    print("\nROUTING METHOD DISTRIBUTION:")
    print("-" * 80)
    for method, count in sorted(routing_usage.items(), key=lambda x: x[1], reverse=True):
        percentage = count / successful_queries * 100 if successful_queries > 0 else 0
        print(f"{method:<35} {count:>5} ({percentage:.1f}%)")

    print("=" * 80)

    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"comprehensive_test_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump({
            "metadata": {
                "total_queries": total_queries,
                "successful": successful_queries,
                "failed": failed_queries,
                "success_rate": successful_queries / total_queries * 100,
                "avg_response_time": total_time / total_queries,
                "total_time": total_time,
                "timestamp": datetime.now().isoformat()
            },
            "category_stats": category_stats,
            "tool_usage": tool_usage,
            "routing_usage": routing_usage,
            "detailed_results": all_results
        }, f, indent=2)

    print(f"\nDetailed results saved to: {results_file}")

    # Sample successful responses
    print("\n" + "=" * 80)
    print("SAMPLE SUCCESSFUL RESPONSES (First 5):")
    print("=" * 80)

    success_samples = [r for r in all_results if r["success"]][:5]
    for sample in success_samples:
        print(f"\nQ: {sample['query']}")
        answer = sample['answer']
        if len(answer) > 150:
            answer = answer[:150] + "..."
        print(f"A: {answer}")

    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)

    return {
        "total": total_queries,
        "successful": successful_queries,
        "failed": failed_queries,
        "success_rate": successful_queries / total_queries * 100 if total_queries > 0 else 0
    }

if __name__ == "__main__":
    try:
        results = run_comprehensive_test()

        # Exit code based on success rate
        if results["success_rate"] >= 95:
            exit(0)  # Excellent
        elif results["success_rate"] >= 90:
            exit(0)  # Good
        elif results["success_rate"] >= 80:
            exit(1)  # Acceptable but needs improvement
        else:
            exit(2)  # Poor, needs attention

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        exit(3)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        exit(4)
