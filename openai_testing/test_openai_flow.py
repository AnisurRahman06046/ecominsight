"""
Test script for OpenRouter flow
Run this to test the complete flow: Question -> Query Generation -> Execution -> Response
"""
import asyncio
import logging
import json
import sys
from orchestrator import openrouter_orchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def test_single_query(question: str, shop_id: str = "1"):
    """Test a single query"""
    print("\n" + "=" * 80)
    print(f"TESTING QUERY: {question}")
    print(f"SHOP ID: {shop_id}")
    print("=" * 80 + "\n")

    result = await openrouter_orchestrator.process_query(
        user_question=question,
        shop_id=shop_id
    )

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Success: {result['success']}")
    print(f"\nNatural Language Answer:")
    print(f"  {result.get('answer', 'N/A')}")

    if result.get('query'):
        print(f"\nGenerated Query:")
        print(f"  Collection: {result['query']['collection']}")
        print(f"  Tool: {result['query']['tool_name']}")
        print(f"  Pipeline: {json.dumps(result['query']['pipeline'], indent=4)}")

    if result.get('data'):
        print(f"\nQuery Results:")
        print(f"  {json.dumps(result['data'], indent=4, default=str)}")

    if result.get('error'):
        print(f"\nError: {result['error']}")

    print("=" * 80 + "\n")

    return result


async def run_test_suite():
    """Run a suite of test queries"""
    test_queries = [
        "What is my total sales today?",
        "How many orders did I receive yesterday?",
        "Show me the top 5 best selling products",
        "What is my average order value this month?",
        "Who are my top 3 customers by spending?",
    ]

    try:
        # Initialize
        await openrouter_orchestrator.initialize()

        # Run each test query
        results = []
        for i, question in enumerate(test_queries, 1):
            print(f"\n{'#' * 80}")
            print(f"TEST {i}/{len(test_queries)}")
            print(f"{'#' * 80}")

            result = await test_single_query(question, shop_id="1")
            results.append({
                "question": question,
                "success": result["success"],
                "answer": result.get("answer")
            })

            # Wait a bit between queries to avoid rate limiting
            if i < len(test_queries):
                print("\nWaiting 2 seconds before next query...")
                await asyncio.sleep(2)

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        successful = sum(1 for r in results if r["success"])
        print(f"Total Tests: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(results) - successful}")
        print("\nResults:")
        for i, r in enumerate(results, 1):
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {i}. {r['question']}")
            if r.get('answer'):
                print(f"      → {r['answer'][:100]}...")
        print("=" * 80)

    finally:
        # Cleanup
        await openrouter_orchestrator.cleanup()


async def interactive_mode():
    """Interactive mode for testing custom queries"""
    print("\n" + "=" * 80)
    print("OPENROUTER INTERACTIVE TEST MODE")
    print("=" * 80)
    print("Enter your questions to test the OpenRouter flow.")
    print("Commands:")
    print("  - Type your question and press Enter")
    print("  - Type 'quit' or 'exit' to exit")
    print("  - Type 'shop <id>' to change shop ID")
    print("=" * 80 + "\n")

    try:
        await openrouter_orchestrator.initialize()

        shop_id = "1"
        print(f"Current shop ID: {shop_id}\n")

        while True:
            try:
                question = input("Your question: ").strip()

                if question.lower() in ['quit', 'exit', 'q']:
                    print("\nExiting...")
                    break

                if question.lower().startswith('shop '):
                    shop_id = question.split(' ', 1)[1].strip()
                    print(f"Shop ID changed to: {shop_id}\n")
                    continue

                if not question:
                    continue

                await test_single_query(question, shop_id)

            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error in interactive mode: {e}")
                print(f"Error: {e}\n")

    finally:
        await openrouter_orchestrator.cleanup()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test OpenRouter flow")
    parser.add_argument(
        '--mode',
        choices=['suite', 'interactive', 'single'],
        default='interactive',
        help='Test mode: suite (run test suite), interactive (ask questions), single (test one query)'
    )
    parser.add_argument(
        '--question',
        type=str,
        help='Question to test (for single mode)'
    )
    parser.add_argument(
        '--shop-id',
        type=str,
        default='1',
        help='Shop ID to use (default: 1)'
    )

    args = parser.parse_args()

    if args.mode == 'suite':
        asyncio.run(run_test_suite())
    elif args.mode == 'interactive':
        asyncio.run(interactive_mode())
    elif args.mode == 'single':
        if not args.question:
            print("Error: --question is required for single mode")
            sys.exit(1)
        asyncio.run(test_single_query(args.question, args.shop_id))


if __name__ == "__main__":
    main()
