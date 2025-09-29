#!/usr/bin/env python3
"""
API Testing Script for EcomInsight
Tests different query types and endpoints
"""

import requests
import json
import time
from typing import Dict, Any
from datetime import datetime

BASE_URL = "http://localhost:8000"
SHOP_ID = "1"  # Change this to your shop ID

def print_response(response: Dict[str, Any], query: str):
    """Pretty print API response"""
    print("\n" + "="*80)
    print(f"📝 QUERY: {query}")
    print("-"*80)
    print(f"✅ ANSWER: {response.get('answer', 'No answer')}")
    print(f"⚡ Query Type: {response.get('query_type', 'unknown')}")
    print(f"⏱️  Processing Time: {response.get('processing_time', 0):.2f}s")
    print(f"💾 Cached: {response.get('cached', False)}")

    if response.get('data'):
        print(f"📊 Data: {json.dumps(response['data'], indent=2)[:200]}...")

    if response.get('metadata'):
        print(f"📋 Metadata: {json.dumps(response['metadata'], indent=2)[:200]}...")
    print("="*80)

def test_endpoint(endpoint: str, query: str, shop_id: str = SHOP_ID):
    """Test a single endpoint with a query"""
    url = f"{BASE_URL}{endpoint}"
    payload = {
        "shop_id": shop_id,
        "question": query,
        "use_cache": False
    }

    print(f"\n🔄 Testing: {endpoint}")
    print(f"   Query: {query}")

    try:
        start_time = time.time()
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        print_response(result, query)
        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

def main():
    print("🚀 EcomInsight API Testing Suite")
    print("="*80)

    # 1. Simple KPI Queries (Template-based) - /api/ask-v2
    print("\n📊 TESTING SIMPLE KPI QUERIES (Template-based)")
    print("-"*80)

    kpi_queries = [
        "How many orders do I have?",
        "What is my total revenue?",
        "How many customers do I have?",
        "What are my top selling products?",
        "What is my average order value?",
    ]

    for query in kpi_queries:
        test_endpoint("/api/ask-v2", query)
        time.sleep(1)  # Prevent overwhelming the server

    # 2. Complex LLM-Generated Queries - /api/ask
    print("\n🧠 TESTING COMPLEX LLM-GENERATED QUERIES")
    print("-"*80)

    complex_queries = [
        "Show me orders from last week with total amount greater than $100 and group them by customer",
        "What is the correlation between product price and order frequency?",
        "Find customers who ordered more than 5 times but haven't ordered in the last 30 days",
        "Calculate the month-over-month growth rate for each product category",
        "Which products are frequently bought together in the same order?",
        "Show me the customer lifetime value distribution across different segments",
        "What's the average time between repeat purchases for my top 10 customers?",
        "Identify seasonal patterns in my sales data",
    ]

    for query in complex_queries:
        test_endpoint("/api/ask", query)
        time.sleep(2)  # LLM queries take longer

    # 3. Analytical RAG Queries - /api/ask
    print("\n📈 TESTING ANALYTICAL RAG QUERIES")
    print("-"*80)

    analytical_queries = [
        "Give me insights about my business performance",
        "Analyze my customer behavior patterns",
        "What trends do you see in my sales data?",
        "Provide recommendations to improve my revenue",
        "Analyze my product performance across categories",
    ]

    for query in analytical_queries:
        test_endpoint("/api/ask", query)
        time.sleep(2)

    # 4. Hybrid Queries - /api/ask-v3
    print("\n🔀 TESTING HYBRID QUERIES")
    print("-"*80)

    hybrid_queries = [
        "What were my sales yesterday?",
        "Show me customer segmentation analysis",
        "Compare this month's performance with last month",
    ]

    for query in hybrid_queries:
        test_endpoint("/api/ask-v3", query)
        time.sleep(1)

    # 5. Edge Cases and Error Handling
    print("\n⚠️  TESTING EDGE CASES")
    print("-"*80)

    edge_queries = [
        "",  # Empty query
        "What is the meaning of life?",  # Irrelevant query
        "SELECT * FROM orders",  # SQL injection attempt
        "Show me data from shop 999999",  # Non-existent shop
    ]

    for query in edge_queries:
        test_endpoint("/api/ask", query if query else "[empty query]")
        time.sleep(1)

    print("\n✅ Testing Complete!")

if __name__ == "__main__":
    main()