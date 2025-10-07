#!/usr/bin/env python3
"""
Test 100 realistic e-commerce queries (simple and complex).
"""
import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:8000/api/mcp/ask"
SHOP_ID = "13"

# 100 realistic e-commerce queries (simple to complex)
TEST_QUERIES = [
    # Simple count queries (20)
    "How many products do I have?",
    "How many orders?",
    "How many customers?",
    "Count my products",
    "Count my orders",
    "Count my customers",
    "Total products",
    "Total orders",
    "Total customers",
    "Number of products",
    "Number of orders",
    "Number of customers",
    "Product count",
    "Order count",
    "Customer count",
    "How many items in catalog?",
    "How many sales?",
    "How many buyers?",
    "Show product count",
    "Show order count",

    # Simple revenue/sales queries (20)
    "What is my total sales?",
    "Total revenue?",
    "Show me revenue",
    "What is my total revenue?",
    "How much did I sell?",
    "Total sales amount?",
    "Give me total sales",
    "What are my total sales?",
    "Show total revenue",
    "How much revenue?",
    "What's my revenue?",
    "Total sales",
    "Revenue",
    "Sales total",
    "My revenue",
    "My sales",
    "Show sales",
    "Display revenue",
    "Total amount",
    "Sales amount",

    # Date-based queries (20)
    "What is my yesterday's total sales?",
    "Yesterday's revenue?",
    "How much did I sell yesterday?",
    "Yesterday sales",
    "Sales from yesterday",
    "What is today's total sales?",
    "Today's revenue?",
    "How much did I sell today?",
    "Today sales",
    "Sales from today",
    "This week sales?",
    "This month sales?",
    "Last week revenue?",
    "Last month revenue?",
    "Sales this week",
    "Sales this month",
    "Revenue this week",
    "Revenue this month",
    "How much yesterday?",
    "How much today?",

    # Top/Best queries (20)
    "What are my top products?",
    "Best selling products?",
    "Show me top sellers",
    "Top 5 products?",
    "Best products?",
    "Most popular products?",
    "Top selling items?",
    "What are my best sellers?",
    "Show best selling products",
    "Who are my top customers?",
    "Best customers?",
    "Show me top spenders",
    "Top 5 customers?",
    "Best buyers?",
    "Most valuable customers?",
    "Top spending customers?",
    "Who spends the most?",
    "Show top customers",
    "Top 10 products",
    "Top 10 customers",

    # Complex analytical queries (20)
    "How many orders did I get this month?",
    "What's my average order value?",
    "How many pending orders?",
    "How many completed orders?",
    "How many cancelled orders?",
    "Orders by status",
    "How many orders today?",
    "How many new customers this month?",
    "Revenue by product category",
    "Which products are not selling?",
    "Customer with highest spending?",
    "Most ordered product?",
    "Least ordered product?",
    "Orders placed last 7 days?",
    "Revenue from last 30 days?",
    "How many repeat customers?",
    "Average revenue per customer?",
    "Products sold today?",
    "Revenue per day this week?",
    "Customer growth this month?",
]


def run_test():
    """Run 100 test queries and collect results."""

    print("="*80)
    print(f"TESTING 100 E-COMMERCE QUERIES")
    print(f"Shop ID: {SHOP_ID}")
    print(f"API: {API_URL}")
    print(f"Started: {datetime.now()}")
    print("="*80)
    print()

    results = []
    successful = 0
    failed = 0
    total_time = 0

    for i, question in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/100] Testing: {question}")

        start_time = time.time()
        try:
            response = requests.post(
                API_URL,
                json={"shop_id": SHOP_ID, "question": question},
                timeout=60
            )
            response_time = time.time() - start_time
            total_time += response_time

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")

                # Simple validation
                is_valid = len(answer) > 0 and "error" not in answer.lower()

                if is_valid:
                    successful += 1
                    status = "✓ SUCCESS"
                else:
                    failed += 1
                    status = "✗ FAILED"

                print(f"  {status} ({response_time:.2f}s)")
                print(f"  Answer: {answer[:100]}{'...' if len(answer) > 100 else ''}")

                results.append({
                    "question": question,
                    "answer": answer,
                    "response_time": response_time,
                    "success": is_valid
                })
            else:
                failed += 1
                print(f"  ✗ FAILED - HTTP {response.status_code}")
                results.append({
                    "question": question,
                    "error": f"HTTP {response.status_code}",
                    "response_time": response_time,
                    "success": False
                })

        except requests.Timeout:
            failed += 1
            response_time = 60
            total_time += response_time
            print(f"  ✗ TIMEOUT (>60s)")
            results.append({
                "question": question,
                "error": "Timeout",
                "response_time": response_time,
                "success": False
            })
        except Exception as e:
            failed += 1
            response_time = time.time() - start_time
            total_time += response_time
            print(f"  ✗ ERROR: {str(e)}")
            results.append({
                "question": question,
                "error": str(e),
                "response_time": response_time,
                "success": False
            })

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Queries:    {len(TEST_QUERIES)}")
    print(f"Successful:       {successful} ({successful/len(TEST_QUERIES)*100:.1f}%)")
    print(f"Failed:           {failed} ({failed/len(TEST_QUERIES)*100:.1f}%)")
    print(f"Avg Response:     {total_time/len(TEST_QUERIES):.2f}s")
    print(f"Total Time:       {total_time:.2f}s")
    print("="*80)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_100_results_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump({
            "summary": {
                "total": len(TEST_QUERIES),
                "successful": successful,
                "failed": failed,
                "success_rate": successful/len(TEST_QUERIES)*100,
                "avg_response_time": total_time/len(TEST_QUERIES),
                "total_time": total_time
            },
            "results": results
        }, f, indent=2)

    print(f"\nResults saved to: {filename}")

    # Show some sample successful answers
    print("\n" + "="*80)
    print("SAMPLE SUCCESSFUL RESPONSES (first 10):")
    print("="*80)
    success_count = 0
    for r in results:
        if r.get("success") and success_count < 10:
            print(f"\nQ: {r['question']}")
            print(f"A: {r['answer']}")
            success_count += 1

    # Show failed queries
    failed_queries = [r for r in results if not r.get("success")]
    if failed_queries:
        print("\n" + "="*80)
        print(f"FAILED QUERIES ({len(failed_queries)}):")
        print("="*80)
        for r in failed_queries[:10]:  # Show first 10
            print(f"\nQ: {r['question']}")
            print(f"Error: {r.get('error', r.get('answer', 'Unknown'))}")


if __name__ == "__main__":
    run_test()
