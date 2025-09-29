#!/bin/bash

# EcomInsight API Testing Examples
# Run these commands to test different query types

echo "🚀 EcomInsight API Test Examples"
echo "================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base URL
BASE_URL="http://localhost:8000"
SHOP_ID="1"

echo -e "\n${BLUE}1. SIMPLE KPI QUERIES (Template-based - Fast)${NC}"
echo "================================================"

echo -e "\n${YELLOW}Query: Total number of orders${NC}"
curl -s -X POST "$BASE_URL/api/ask-v2" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "How many orders do I have?",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${YELLOW}Query: Total revenue${NC}"
curl -s -X POST "$BASE_URL/api/ask-v2" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "What is my total revenue?",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${BLUE}2. COMPLEX LLM-GENERATED QUERIES${NC}"
echo "================================="

echo -e "\n${YELLOW}Query: Orders with conditions and grouping${NC}"
curl -s -X POST "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "Show me all orders from the last 7 days with total amount greater than $50, grouped by status",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${YELLOW}Query: Complex aggregation${NC}"
curl -s -X POST "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "What is the average order value for each product category, sorted by revenue?",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${YELLOW}Query: Customer analysis${NC}"
curl -s -X POST "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "Find my top 10 customers by total spending and show their order count",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${BLUE}3. ANALYTICAL RAG QUERIES${NC}"
echo "========================="

echo -e "\n${YELLOW}Query: Business insights${NC}"
curl -s -X POST "$BASE_URL/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "Give me analytical insights about my sales trends",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${BLUE}4. HYBRID QUERIES${NC}"
echo "=================="

echo -e "\n${YELLOW}Query: Mixed intent${NC}"
curl -s -X POST "$BASE_URL/api/ask-v3" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "'$SHOP_ID'",
    "question": "Compare my sales performance this month versus last month",
    "use_cache": false
  }' | python -m json.tool

echo -e "\n${GREEN}✅ Testing complete!${NC}"