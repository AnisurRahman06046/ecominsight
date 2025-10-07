#!/bin/bash

echo "=========================================="
echo "Testing E-commerce Analytics API"
echo "=========================================="
echo ""

queries=(
    "How many orders do I have?"
    "What is my total revenue?"
    "Show me top 3 best selling products"
    "Who are my top 5 customers?"
    "What was yesterday's total sales?"
    "How many orders did I get last week?"
    "What is my average order value?"
    "Show me revenue from last month"
    "How many pending orders?"
    "Top 10 products"
    "What is today's revenue?"
    "Give me total sales this month"
)

for query in "${queries[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Q: $query"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    start_time=$(date +%s.%N)
    
    response=$(curl -s -X POST "http://localhost:8000/api/mcp/ask" \
        -H "Content-Type: application/json" \
        -d "{\"shop_id\": \"13\", \"question\": \"$query\"}")
    
    end_time=$(date +%s.%N)
    time_taken=$(echo "$end_time - $start_time" | bc)
    
    answer=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('answer', 'ERROR'))" 2>/dev/null)
    
    echo "A: $answer"
    echo "⏱️  Response time: ${time_taken}s"
    echo ""
done

echo "=========================================="
echo "Test completed!"
echo "=========================================="
