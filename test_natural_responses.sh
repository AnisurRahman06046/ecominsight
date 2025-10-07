#!/bin/bash
queries=(
    "What is my total revenue?"
    "What is the total sales of yesterday?"
    "Last week revenue"
    "Today's sales"
    "Show me revenue this month"
)

for query in "${queries[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Q: $query"
    response=$(curl -s -X POST "http://localhost:8000/api/mcp/ask" \
        -H "Content-Type: application/json" \
        -d "{\"shop_id\": \"13\", \"question\": \"$query\"}")
    answer=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('answer', 'ERROR'))" 2>/dev/null || echo "ERROR")
    echo "A: $answer"
    echo ""
done
