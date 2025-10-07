#!/usr/bin/env python3
"""
Evaluation script for testing the model with 5000 queries.
Tests various query types and tracks failures, incorrect responses, and hallucinations.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random
from collections import defaultdict

# API endpoint
API_URL = "http://localhost:8000/api/mcp/ask"

# Shop ID to use for testing
SHOP_ID = "13"

# Query templates for different types
QUERY_TEMPLATES = {
    "count_products": [
        "How many products do I have?",
        "Count my products",
        "Total products?",
        "Number of products?",
        "Product count?",
        "How many items in my catalog?",
        "Show product count",
        "Tell me product count",
        "What is my product count?",
        "Give me product count"
    ],
    "count_orders": [
        "How many orders do I have?",
        "Count my orders",
        "Total orders?",
        "Number of orders?",
        "Order count?",
        "How many sales?",
        "Show order count",
        "Tell me order count",
        "What is my order count?",
        "Give me order count"
    ],
    "count_customers": [
        "How many customers do I have?",
        "Count my customers",
        "Total customers?",
        "Number of customers?",
        "Customer count?",
        "How many buyers?",
        "Show customer count",
        "Tell me customer count",
        "What is my customer count?",
        "Give me customer count"
    ],
    "total_sales": [
        "What is my total sales?",
        "Total revenue?",
        "How much did I sell?",
        "Show me revenue",
        "What is my total revenue?",
        "Give me total sales",
        "Total sales amount?",
        "Show total revenue",
        "How much revenue?",
        "What are my total sales?"
    ],
    "yesterday_sales": [
        "What is my yesterday's total sales?",
        "Yesterday's revenue?",
        "How much did I sell yesterday?",
        "Show me yesterday's sales",
        "Yesterday sales?",
        "Sales from yesterday?",
        "Revenue yesterday?",
        "What was yesterday's revenue?",
        "Give me yesterday's total",
        "How much yesterday?"
    ],
    "today_sales": [
        "What is my today's total sales?",
        "Today's revenue?",
        "How much did I sell today?",
        "Show me today's sales",
        "Today sales?",
        "Sales from today?",
        "Revenue today?",
        "What is today's revenue?",
        "Give me today's total",
        "How much today?"
    ],
    "best_products": [
        "What are my top products?",
        "Best selling products?",
        "Show me top sellers",
        "Which products sell the most?",
        "Top 5 products?",
        "Best products?",
        "Most popular products?",
        "Top selling items?",
        "What are my best sellers?",
        "Show best selling products"
    ],
    "top_customers": [
        "Who are my top customers?",
        "Best customers?",
        "Show me top spenders",
        "Which customers spend the most?",
        "Top 5 customers?",
        "Best buyers?",
        "Most valuable customers?",
        "Top spending customers?",
        "Who spends the most?",
        "Show top customers"
    ]
}

# Expected response patterns for validation
EXPECTED_PATTERNS = {
    "count_products": {
        "must_contain": ["product"],
        "must_have_number": True,
        "number_range": (1, 100000),
        "should_not_contain": ["order", "customer", "people", "politician", "votes"]
    },
    "count_orders": {
        "must_contain": ["order"],
        "must_have_number": True,
        "number_range": (1, 100000),
        "should_not_contain": ["product", "customer", "people", "politician"]
    },
    "count_customers": {
        "must_contain": ["customer"],
        "must_have_number": True,
        "number_range": (1, 100000),
        "should_not_contain": ["product", "order", "politician", "votes"]
    },
    "total_sales": {
        "must_contain": ["$", "total"],
        "must_have_number": True,
        "number_range": (0, 100000000),
        "should_not_contain": ["people", "politician", "votes"]
    },
    "yesterday_sales": {
        "must_contain": ["$"],
        "must_have_number": True,
        "number_range": (0, 1000000),
        "should_not_contain": ["people", "politician", "votes"]
    },
    "today_sales": {
        "must_contain": ["$"],
        "must_have_number": True,
        "number_range": (0, 1000000),
        "should_not_contain": ["people", "politician", "votes"]
    },
    "best_products": {
        "must_contain": ["product"],
        "must_have_number": False,
        "should_not_contain": ["people", "politician", "customer"]
    },
    "top_customers": {
        "must_contain": ["customer"],
        "must_have_number": False,
        "should_not_contain": ["people", "politician", "product"]
    }
}


class QueryEvaluator:
    def __init__(self, total_queries: int = 5000):
        self.total_queries = total_queries
        self.results = []
        self.failed_queries = []
        self.hallucinated_queries = []
        self.incorrect_queries = []
        self.stats = defaultdict(int)

    async def run_query(self, session: aiohttp.ClientSession, question: str, query_type: str) -> Dict[str, Any]:
        """Run a single query against the API."""
        start_time = time.time()

        try:
            async with session.post(
                API_URL,
                json={"shop_id": SHOP_ID, "question": question},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response_time = time.time() - start_time

                if response.status != 200:
                    return {
                        "question": question,
                        "query_type": query_type,
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "response_time": response_time
                    }

                data = await response.json()

                return {
                    "question": question,
                    "query_type": query_type,
                    "success": True,
                    "answer": data.get("answer"),
                    "response_time": response_time,
                    "metadata": data.get("metadata", {})
                }

        except asyncio.TimeoutError:
            return {
                "question": question,
                "query_type": query_type,
                "success": False,
                "error": "Timeout",
                "response_time": 30.0
            }
        except Exception as e:
            return {
                "question": question,
                "query_type": query_type,
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }

    def validate_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if the response is correct and not hallucinated."""
        if not result.get("success"):
            return {"valid": False, "reason": "API failed"}

        answer = result.get("answer", "").lower()
        query_type = result.get("query_type")

        if not answer:
            return {"valid": False, "reason": "Empty answer"}

        validation = {"valid": True, "issues": []}

        # Get expected patterns for this query type
        patterns = EXPECTED_PATTERNS.get(query_type, {})

        # Check must_contain patterns
        must_contain = patterns.get("must_contain", [])
        for pattern in must_contain:
            if pattern.lower() not in answer:
                validation["valid"] = False
                validation["issues"].append(f"Missing required keyword: '{pattern}'")

        # Check should_not_contain patterns (hallucination indicators)
        should_not_contain = patterns.get("should_not_contain", [])
        for pattern in should_not_contain:
            if pattern.lower() in answer:
                validation["valid"] = False
                validation["issues"].append(f"Hallucination detected: '{pattern}'")

        # Check if number is present when required
        if patterns.get("must_have_number"):
            import re
            numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', answer)
            if not numbers:
                validation["valid"] = False
                validation["issues"].append("Missing required number")
            else:
                # Validate number range
                number_range = patterns.get("number_range")
                if number_range:
                    try:
                        num = float(numbers[0].replace(",", ""))
                        if not (number_range[0] <= num <= number_range[1]):
                            validation["valid"] = False
                            validation["issues"].append(f"Number {num} out of expected range {number_range}")
                    except:
                        pass

        return validation

    async def run_evaluation(self):
        """Run the full evaluation."""
        print(f"Starting evaluation with {self.total_queries} queries...")
        print(f"Testing shop_id: {SHOP_ID}")
        print("=" * 80)

        # Generate query list
        queries = []
        query_types = list(QUERY_TEMPLATES.keys())
        queries_per_type = self.total_queries // len(query_types)

        for query_type in query_types:
            templates = QUERY_TEMPLATES[query_type]
            for i in range(queries_per_type):
                question = random.choice(templates)
                queries.append((question, query_type))

        # Add remaining queries to reach exact total
        remaining = self.total_queries - len(queries)
        for i in range(remaining):
            query_type = random.choice(query_types)
            question = random.choice(QUERY_TEMPLATES[query_type])
            queries.append((question, query_type))

        # Shuffle queries
        random.shuffle(queries)

        print(f"Generated {len(queries)} test queries")
        print(f"Queries per type: ~{queries_per_type}")
        print()

        # Run queries with concurrency control
        connector = aiohttp.TCPConnector(limit=5)  # Max 5 concurrent requests
        async with aiohttp.ClientSession(connector=connector) as session:
            batch_size = 50
            total_batches = (len(queries) + batch_size - 1) // batch_size

            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(queries))
                batch = queries[start_idx:end_idx]

                # Run batch
                tasks = [self.run_query(session, q, qt) for q, qt in batch]
                batch_results = await asyncio.gather(*tasks)

                # Process results
                for result in batch_results:
                    self.results.append(result)

                    # Update stats
                    if result.get("success"):
                        self.stats["success"] += 1

                        # Validate response
                        validation = self.validate_response(result)
                        if validation["valid"]:
                            self.stats["valid"] += 1
                        else:
                            self.stats["invalid"] += 1

                            # Categorize the issue
                            issues = validation.get("issues", [])
                            if any("Hallucination" in issue for issue in issues):
                                self.hallucinated_queries.append({
                                    **result,
                                    "validation": validation
                                })
                                self.stats["hallucinated"] += 1
                            else:
                                self.incorrect_queries.append({
                                    **result,
                                    "validation": validation
                                })
                                self.stats["incorrect"] += 1
                    else:
                        self.stats["failed"] += 1
                        self.failed_queries.append(result)

                # Progress update
                completed = len(self.results)
                progress = (completed / self.total_queries) * 100
                print(f"Progress: {completed}/{self.total_queries} ({progress:.1f}%) | "
                      f"Success: {self.stats['success']} | "
                      f"Valid: {self.stats['valid']} | "
                      f"Invalid: {self.stats['invalid']} | "
                      f"Failed: {self.stats['failed']}")

                # Small delay between batches
                await asyncio.sleep(0.1)

        print()
        print("Evaluation complete!")
        print("=" * 80)

    def generate_report(self):
        """Generate evaluation report."""
        total = len(self.results)

        report = f"""
{'=' * 80}
EVALUATION REPORT
{'=' * 80}

SUMMARY:
--------
Total Queries:     {total}
Successful:        {self.stats['success']} ({self.stats['success']/total*100:.2f}%)
Valid Responses:   {self.stats['valid']} ({self.stats['valid']/total*100:.2f}%)
Invalid Responses: {self.stats['invalid']} ({self.stats['invalid']/total*100:.2f}%)
Failed Queries:    {self.stats['failed']} ({self.stats['failed']/total*100:.2f}%)

ISSUES BREAKDOWN:
-----------------
Hallucinated:      {self.stats['hallucinated']} ({self.stats['hallucinated']/total*100:.2f}%)
Incorrect:         {self.stats['incorrect']} ({self.stats['incorrect']/total*100:.2f}%)
API Failures:      {self.stats['failed']} ({self.stats['failed']/total*100:.2f}%)

PERFORMANCE:
------------
"""

        # Calculate average response times
        response_times = [r["response_time"] for r in self.results if r.get("success")]
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            report += f"Average Response Time: {avg_time:.3f}s\n"
            report += f"Min Response Time:     {min_time:.3f}s\n"
            report += f"Max Response Time:     {max_time:.3f}s\n"

        # Query type breakdown
        report += f"\nQUERY TYPE BREAKDOWN:\n"
        report += f"{'-' * 80}\n"

        type_stats = defaultdict(lambda: {"total": 0, "valid": 0, "invalid": 0})
        for result in self.results:
            if result.get("success"):
                qtype = result.get("query_type")
                type_stats[qtype]["total"] += 1

                validation = self.validate_response(result)
                if validation["valid"]:
                    type_stats[qtype]["valid"] += 1
                else:
                    type_stats[qtype]["invalid"] += 1

        for qtype, stats in sorted(type_stats.items()):
            total_type = stats["total"]
            valid_rate = (stats["valid"] / total_type * 100) if total_type > 0 else 0
            report += f"{qtype:25s}: {stats['valid']:4d}/{total_type:4d} valid ({valid_rate:5.1f}%)\n"

        # Sample hallucinations
        if self.hallucinated_queries:
            report += f"\nSAMPLE HALLUCINATIONS (showing first 10):\n"
            report += f"{'-' * 80}\n"
            for i, result in enumerate(self.hallucinated_queries[:10], 1):
                report += f"\n{i}. Question: {result['question']}\n"
                report += f"   Answer: {result['answer']}\n"
                report += f"   Issues: {', '.join(result['validation']['issues'])}\n"

        # Sample incorrect responses
        if self.incorrect_queries:
            report += f"\nSAMPLE INCORRECT RESPONSES (showing first 10):\n"
            report += f"{'-' * 80}\n"
            for i, result in enumerate(self.incorrect_queries[:10], 1):
                report += f"\n{i}. Question: {result['question']}\n"
                report += f"   Answer: {result['answer']}\n"
                report += f"   Issues: {', '.join(result['validation']['issues'])}\n"

        report += f"\n{'=' * 80}\n"

        return report

    def save_results(self):
        """Save detailed results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save all results
        with open(f"evaluation_results_{timestamp}.json", "w") as f:
            json.dump({
                "stats": dict(self.stats),
                "results": self.results
            }, f, indent=2)

        # Save problematic queries for few-shot learning
        problematic = {
            "hallucinated": self.hallucinated_queries,
            "incorrect": self.incorrect_queries,
            "failed": self.failed_queries
        }

        with open(f"problematic_queries_{timestamp}.json", "w") as f:
            json.dump(problematic, f, indent=2)

        print(f"\nResults saved:")
        print(f"  - evaluation_results_{timestamp}.json")
        print(f"  - problematic_queries_{timestamp}.json")


async def main():
    import sys
    total_queries = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    evaluator = QueryEvaluator(total_queries=total_queries)
    await evaluator.run_evaluation()

    # Generate and print report
    report = evaluator.generate_report()
    print(report)

    # Save results
    evaluator.save_results()

    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"evaluation_report_{timestamp}.txt", "w") as f:
        f.write(report)
    print(f"  - evaluation_report_{timestamp}.txt")


if __name__ == "__main__":
    asyncio.run(main())
