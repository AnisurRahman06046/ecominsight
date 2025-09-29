#!/usr/bin/env python3
"""
Test LLM's ability to generate complex MongoDB queries
This script tests various query patterns to verify LLM understanding
"""

import requests
import json
import time
from typing import Dict, Any, List
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

class LLMQueryTester:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def test_query(self, query: str, expected_operations: List[str], description: str):
        """Test a query and check if it generates expected MongoDB operations"""
        print(f"\n{Fore.YELLOW}{'='*80}")
        print(f"{Fore.CYAN}Test: {description}")
        print(f"{Fore.YELLOW}{'='*80}")
        print(f"Query: {query}")
        print(f"Expected operations: {expected_operations}")

        try:
            response = requests.post(
                f"{BASE_URL}/api/ask",
                json={
                    "shop_id": SHOP_ID,
                    "question": query,
                    "use_cache": False
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            # Extract the generated pipeline
            pipeline = result.get("metadata", {}).get("generated_pipeline", [])

            # Check what operations were generated
            operations = []
            for stage in pipeline:
                operations.extend(stage.keys())

            print(f"\nGenerated Pipeline:")
            print(json.dumps(pipeline, indent=2))

            # Check if expected operations are present
            success = True
            missing_ops = []
            for expected_op in expected_operations:
                if expected_op not in operations:
                    success = False
                    missing_ops.append(expected_op)

            if success:
                print(f"{Fore.GREEN}✅ PASSED - All expected operations found")
                self.passed += 1
            else:
                print(f"{Fore.RED}❌ FAILED - Missing operations: {missing_ops}")
                print(f"{Fore.RED}   Found operations: {operations}")
                self.failed += 1

            # Show sample data
            if result.get("data"):
                data_count = len(result["data"]) if isinstance(result["data"], list) else 1
                print(f"\n{Fore.CYAN}Result: {data_count} records returned")
                print(f"Answer: {result.get('answer', 'N/A')[:100]}...")

            self.results.append({
                "query": query,
                "description": description,
                "success": success,
                "pipeline": pipeline,
                "missing_ops": missing_ops if not success else []
            })

            return success

        except Exception as e:
            print(f"{Fore.RED}❌ ERROR: {e}")
            self.failed += 1
            self.results.append({
                "query": query,
                "description": description,
                "success": False,
                "error": str(e)
            })
            return False

def main():
    print(f"{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}LLM Complex Query Testing Suite")
    print(f"{Fore.MAGENTA}Testing MongoDB query generation capabilities")
    print(f"{Fore.MAGENTA}{'='*80}")

    tester = LLMQueryTester()

    # Test cases with expected MongoDB operations
    test_cases = [
        {
            "query": "Count all orders for shop 1",
            "expected": ["$match", "$count"],
            "description": "Simple count with filter"
        },
        {
            "query": "Show me orders with grand_total greater than 1000",
            "expected": ["$match"],
            "description": "Filter with comparison operator"
        },
        {
            "query": "Get the top 5 orders by grand_total amount",
            "expected": ["$match", "$sort", "$limit"],
            "description": "Sorting and limiting"
        },
        {
            "query": "Group orders by status and count them",
            "expected": ["$match", "$group"],
            "description": "Group by with count"
        },
        {
            "query": "Calculate total revenue by summing all grand_total values",
            "expected": ["$match", "$group"],
            "description": "Aggregation with sum"
        },
        {
            "query": "Find orders from the last 30 days",
            "expected": ["$match"],
            "description": "Date range filter"
        },
        {
            "query": "Show average order value by customer",
            "expected": ["$match", "$group"],
            "description": "Group by customer with average"
        },
        {
            "query": "Find orders with status 'completed' and grand_total over 500",
            "expected": ["$match"],
            "description": "Multiple filter conditions"
        },
        {
            "query": "Count orders by month",
            "expected": ["$match", "$group"],
            "description": "Date grouping"
        },
        {
            "query": "Show top 3 customers by total spending",
            "expected": ["$match", "$group", "$sort", "$limit"],
            "description": "Complex aggregation with multiple stages"
        }
    ]

    print(f"\n{Fore.CYAN}Running {len(test_cases)} test cases...")
    print(f"{Fore.CYAN}This will test if the LLM can generate appropriate MongoDB operations")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{Fore.YELLOW}Test {i}/{len(test_cases)}")
        tester.test_query(
            test_case["query"],
            test_case["expected"],
            test_case["description"]
        )
        time.sleep(1)  # Rate limiting

    # Print summary
    print(f"\n{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.MAGENTA}TEST SUMMARY")
    print(f"{Fore.MAGENTA}{'='*80}")
    print(f"{Fore.GREEN}Passed: {tester.passed}")
    print(f"{Fore.RED}Failed: {tester.failed}")
    print(f"Total: {len(test_cases)}")
    print(f"Success Rate: {(tester.passed/len(test_cases)*100):.1f}%")

    # Detailed failure analysis
    if tester.failed > 0:
        print(f"\n{Fore.RED}Failed Tests Details:")
        for result in tester.results:
            if not result.get("success"):
                print(f"\n{Fore.YELLOW}Query: {result['query']}")
                print(f"Description: {result['description']}")
                if "missing_ops" in result:
                    print(f"{Fore.RED}Missing operations: {result['missing_ops']}")
                if "error" in result:
                    print(f"{Fore.RED}Error: {result['error']}")
                if "pipeline" in result:
                    print(f"Generated: {json.dumps(result['pipeline'], indent=2)}")

    # Recommendations
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}RECOMMENDATIONS")
    print(f"{Fore.CYAN}{'='*80}")

    if tester.passed < len(test_cases) * 0.5:
        print(f"{Fore.YELLOW}⚠️  The LLM is struggling with complex queries.")
        print(f"\nSuggested actions:")
        print(f"1. Try a more capable model (e.g., Llama 3 70B)")
        print(f"2. Improve prompt engineering with more examples")
        print(f"3. Add query preprocessing to help the LLM")
        print(f"4. Consider using query templates for common patterns")
    elif tester.passed < len(test_cases) * 0.8:
        print(f"{Fore.YELLOW}⚠️  The LLM handles basic queries but struggles with complex ones.")
        print(f"\nSuggested improvements:")
        print(f"1. Add more specific examples in the prompt")
        print(f"2. Fine-tune the model on MongoDB queries")
        print(f"3. Implement query validation and correction")
    else:
        print(f"{Fore.GREEN}✅ The LLM is performing well with complex queries!")

    return tester.passed, tester.failed

if __name__ == "__main__":
    try:
        passed, failed = main()
        exit(0 if failed == 0 else 1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Testing interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Testing failed: {e}")
        exit(1)