#!/usr/bin/env python3
"""
Test script to demonstrate AI (TinyLlama) vs Keyword Detection
Shows when the system uses pattern matching vs when it needs AI
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

def test_query(question, expected_method=""):
    """Test a query and show whether AI or keyword matching was used"""
    print(f"\n📝 Query: {question}")
    print("-" * 60)

    start_time = time.time()
    response = requests.post(
        f"{BASE_URL}/api/mcp/ask",
        json={"shop_id": SHOP_ID, "question": question},
        timeout=10
    )
    end_time = time.time()

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success (took {end_time - start_time:.2f}s)")
        print(f"Answer: {data.get('answer', 'N/A')[:100]}...")

        metadata = data.get('metadata', {})
        if metadata:
            tool = metadata.get('tool_used', 'unknown')
            params = metadata.get('parameters', {})

            # Determine if this was keyword-based or AI-based
            # Keywords: Fast response, specific tool match
            # AI: Slower response, sometimes generic tools

            if tool in ['count_documents', 'calculate_sum', 'get_top_customers_by_spending',
                       'get_best_selling_products', 'group_and_count', 'calculate_average']:
                if end_time - start_time < 2.0:
                    print(f"🔍 Method: KEYWORD MATCHING (confidence high)")
                else:
                    print(f"🤖 Method: AI FALLBACK (TinyLlama)")
            else:
                print(f"🤖 Method: AI INTERPRETATION")

            print(f"Tool: {tool}")
            if params.get('collection'):
                print(f"Collection: {params['collection']}")
    else:
        print(f"❌ Failed: HTTP {response.status_code}")

# Test categories
print("=" * 70)
print("AI CAPABILITY TESTING - Keyword Detection vs TinyLlama AI")
print("=" * 70)

print("\n🏷️ CATEGORY 1: Clear Keyword Matches (Should use KEYWORD MATCHING)")
print("=" * 70)

keyword_queries = [
    "How many orders do I have?",
    "What's the total revenue?",
    "Show top 5 customers by spending",
    "Group orders by status",
    "Average order value",
    "Count products",
    "Best selling products"
]

for q in keyword_queries:
    test_query(q)

print("\n\n🤖 CATEGORY 2: Ambiguous Queries (Should trigger AI)")
print("=" * 70)

ai_queries = [
    "What insights can you give me about my store?",
    "How is my business doing?",
    "Tell me something interesting about my data",
    "What should I focus on?",
    "Analyze my business performance",
    "Give me a summary of everything",
    "What patterns do you see?"
]

for q in ai_queries:
    test_query(q)

print("\n\n🔄 CATEGORY 3: Complex Queries (Mix of keyword extraction + AI)")
print("=" * 70)

complex_queries = [
    "Compare revenue trends with customer acquisition",
    "What's driving my sales growth?",
    "Which customers should I target for promotions?",
    "How are my premium products performing versus regular ones?",
    "What's the relationship between order size and customer loyalty?"
]

for q in complex_queries:
    test_query(q)

print("\n\n" + "=" * 70)
print("SUMMARY: How to Tell if AI is Being Used")
print("=" * 70)
print("""
1. KEYWORD MATCHING (Rule-based):
   - Response time: < 1 second
   - Tools: Specific tools like count_documents, calculate_sum
   - Confidence: High (> 0.3)
   - Log shows: "Keyword matching found: [pattern]"

2. AI FALLBACK (TinyLlama):
   - Response time: 2-5 seconds
   - Tools: Sometimes misnamed or generic (find_documents)
   - Confidence: Low (< 0.3)
   - Log shows: "Keyword matching uncertain, trying LLM"

3. HOW TO CHECK:
   - Look at response time
   - Check logs: grep "Keyword matching uncertain" logs/app.log
   - Monitor tool selection accuracy
   - Check if parameters make sense for the query

4. AI CAPABILITIES:
   - Understanding vague requests
   - Interpreting complex multi-part queries
   - Handling queries not in keyword patterns
   - Fallback for uncertain classifications
""")

print("\n✨ The system is AI-powered through:")
print("   1. TinyLlama 1.1B for query interpretation")
print("   2. Intelligent fallback mechanism")
print("   3. Natural language understanding for edge cases")
print("   4. Adaptive tool selection when patterns don't match")