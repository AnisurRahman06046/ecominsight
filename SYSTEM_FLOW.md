# EcomInsight System Flow

## Architecture Overview

```
User Query → FastAPI → MCP Orchestrator → MongoDB Tools → Results → NL Response
                ↓                ↓
            TinyLLama      Fallback Logic
```

## Detailed Flow

### 1. User Input
- Natural language question (e.g., "What's my total revenue?")
- Shop ID for multi-tenant filtering

### 2. API Endpoint (`/api/mcp/ask`)
- Receives POST request with question and shop_id
- Routes to MCP Orchestrator

### 3. MCP Orchestrator Flow

#### Step 3.1: Tool Decision
```python
Try:
    1. Send simplified prompt to TinyLlama (1.1B model)
    2. Ask LLM to choose appropriate tool
Catch (if LLM fails):
    3. Use keyword-based fallback
```

#### Step 3.2: Keyword Fallback Logic
```python
if "how many" or "count" in question:
    → use count_documents tool
elif "total revenue" or "sum" in question:
    → use calculate_sum tool
elif "average" in question:
    → use calculate_average tool
elif "group" or "by status" in question:
    → use group_and_count tool
elif "top" or "best" in question:
    → use get_top_n or get_top_customers_by_spending
elif "last" or "recent" in question:
    → use get_date_range tool
else:
    → use find_documents tool
```

### 4. MongoDB MCP Tools

Available tools:
- `count_documents`: Count items in collection
- `find_documents`: Search with filters and sorting
- `group_and_count`: Group by field and count
- `calculate_sum`: Sum numeric fields
- `calculate_average`: Calculate averages
- `get_top_n`: Get top N documents
- `get_date_range`: Filter by date range
- `get_top_customers_by_spending`: Special customer analysis

Each tool:
1. Builds MongoDB aggregation pipeline
2. Executes on specified collection
3. Returns structured results

### 5. Result Processing
```python
Tool returns → {
    "success": true,
    "data": [results],
    "message": "formatted message"
}
```

### 6. Natural Language Response
- Format results into human-readable answer
- Return to user with metadata

## Example Flows

### Simple Query: "How many orders?"
```
1. User asks: "How many orders?"
2. Keyword detection: "how many" → count_documents
3. Execute: db.order.aggregate([{$match: {shop_id: 10}}, {$count: "total"}])
4. Result: {"total": 174}
5. Response: "You have 174 orders."
```

### Complex Query: "Top 5 customers by spending"
```
1. User asks: "Top 5 customers by spending"
2. Keyword detection: "top" + "customers" → get_top_customers_by_spending
3. Execute: Complex aggregation with $group, $sum, $sort, $limit, $lookup
4. Result: [{"user_id": 2, "total_spent": 77434, "name": "Ashadul Islam"}, ...]
5. Response: "Top customers by spending:\n1. Ashadul Islam: $77,434.00\n..."
```

## Memory Usage (8GB RAM System)

- TinyLlama model: ~637MB
- FastAPI server: ~100-200MB
- MongoDB connection: ~50MB
- Total: <1GB (perfect for 8GB RAM)

## Advantages of MCP Approach

1. **Reliability**: Tools have defined parameters, no syntax errors
2. **Accuracy**: Direct MongoDB operations, not LLM-generated queries
3. **Performance**: Optimized pipelines, proper indexing
4. **Maintainability**: Easy to add new tools
5. **Low Memory**: Works on 8GB RAM with TinyLlama