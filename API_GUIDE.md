# API Guide & Examples

Complete guide for using the E-Commerce Insights Server API with real-world examples and best practices.

## 🚀 Quick Start

### Base URL
```
http://localhost:8000
```

### Authentication
Currently no authentication required. In production, implement API keys or JWT tokens.

## 📡 Core Endpoints

### 1. Ask Endpoint

**POST** `/api/ask` - Process natural language queries

#### Request Format
```json
{
  "shop_id": "10",                    // Required: Shop identifier (string)
  "question": "How many orders today?", // Required: Natural language query
  "context": {                        // Optional: Additional context
    "time_zone": "UTC",
    "currency": "USD"
  },
  "use_cache": true                   // Optional: Enable caching (default: true)
}
```

#### Response Format
```json
{
  "shop_id": "10",
  "question": "How many orders today?",
  "answer": "You have 23 orders today with total value $1,847.50",
  "data": [...],                      // Raw query results
  "query_type": "kpi",               // "kpi" | "unknown" | "analytical"
  "processing_time": 0.234,          // Seconds
  "cached": false,                   // Whether result was cached
  "metadata": {                      // Query-specific metadata
    "kpi": "order_count",
    "params": {"time_period": "today"},
    "pipeline": [...]
  }
}
```

### 2. Health Check

**GET** `/health` - Service health status

#### Response Format
```json
{
  "status": "healthy",
  "timestamp": "2025-09-25T08:00:00Z",
  "services": {
    "database": "connected",          // MongoDB status
    "ollama": "available",           // LLM service status
    "cache": "connected",            // Redis status
    "formatter": "initialized"       // HuggingFace status
  },
  "version": "1.0.0"
}
```

## 💬 Query Examples by Category

### KPI Queries (Fast: <1 second)

These queries use pre-built templates for instant responses:

```bash
# Order Analytics
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "How many orders do I have?"}'

curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "What is my total revenue?"}'

curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "Orders this month?"}'
```

**Expected Responses:**
```json
{
  "answer": "Result: 174",
  "query_type": "kpi",
  "processing_time": 0.08
}

{
  "answer": "Total revenue: $52,847.50",
  "query_type": "kpi",
  "processing_time": 0.12
}
```

### LLM Queries (Medium: 5-15 seconds)

Complex queries that require dynamic MongoDB pipeline generation:

```bash
# Complex Filtering
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "Show me orders over $500"}'

curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "Find customers from Dhaka"}'

# Business Intelligence
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "Show me recent orders"}'
```

**Expected Responses:**
```json
{
  "answer": "Found 10 orders with total value $3,957.00 (avg $395.70). Most common status: Order Placed (10 orders)",
  "query_type": "unknown",
  "processing_time": 8.4,
  "data": [...],
  "metadata": {
    "generated_pipeline": [
      {"$match": {"shop_id": 10}},
      {"$sort": {"created_at": -1}},
      {"$limit": 10}
    ],
    "collection": "order"
  }
}
```

### RAG Analytics (Advanced: 15-25 seconds)

Analytical queries that provide insights and recommendations:

```bash
# Trend Analysis
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "Why are sales declining?"}'

# Strategic Insights
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "How can I improve customer retention?"}'
```

## 🔄 Response Types & Formatting

### Before vs After HuggingFace Integration

#### Before (Raw Data Dump)
```json
{
  "answer": "Found 5 results: 1715020640655, 1715338373990, 1715619528464, 1715173697837, 1715133188987",
  "processing_time": 67.3
}
```

#### After (Human-Readable Insights)
```json
{
  "answer": "Found 10 orders with total value $3,957.00 (avg $395.70). Most common status: Order Placed (10 orders)",
  "processing_time": 28.4
}
```

### Data-Specific Formatting

#### Order Data
```json
// Single Order
{
  "answer": "Order #1758964655092: $390.00 from Azher Uddin Ahmed, Status: Order Placed"
}

// Multiple Orders (Summary)
{
  "answer": "Here are your 5 most recent orders: #1758964655092 ($390 - Azher), #1758985526174 ($390 - Azher), #1753037309789 ($420 - Ashadul)"
}

// Large Dataset (Aggregated)
{
  "answer": "Found 174 orders with total value $52,847.50 (avg $303.70). Most common status: Order Placed (156 orders)"
}
```

#### Product Data
```json
// Single Product
{
  "answer": "Product: Safety Helmet Pro, Price: $45.99, Stock: 150, Status: active"
}

// Product Summary
{
  "answer": "Found 141 products: Safety Helmet Pro ($45.99), Work Boots Heavy Duty ($89.99), Reflective Vest ($24.99), Hard Hat Yellow ($32.50), Safety Goggles ($18.75)"
}

// Product Analytics
{
  "answer": "Found 141 products. 128 active. Price range: $5.99 - $299.99 (avg $67.45)"
}
```

#### Customer Data
```json
// Single Customer
{
  "answer": "Customer: John Smith, Email: john@example.com, Phone: +1234567890"
}

// Customer Summary
{
  "answer": "Found 23 customers: John Smith, Jane Doe, Mike Johnson, Sarah Wilson, David Brown"
}

// Customer Analytics
{
  "answer": "Found 23 customers. Top location: Dhaka (8 customers)"
}
```

## ⚡ Performance Optimization Tips

### 1. Caching Strategy

```bash
# First query (cache miss)
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "How many orders?"}'
# Response: "cached": false, "processing_time": 0.08

# Second identical query (cache hit)
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "How many orders?"}'
# Response: "cached": true, "processing_time": 0.01
```

### 2. Query Optimization

#### Good Practices
```bash
# Specific and clear
"Show me orders from last week"

# Include relevant context
"Find high-value customers over $1000"

# Use business terminology
"Products running low on inventory"
```

#### Avoid
```bash
# Too vague
"Show me stuff"

# Ambiguous timeframes
"Recent things"

# Technical jargon
"SELECT * FROM orders WHERE..."
```

### 3. Batch Processing

For multiple related queries, consider batching:

```python
import asyncio
import httpx

async def batch_queries():
    queries = [
        {"shop_id": "10", "question": "How many orders today?"},
        {"shop_id": "10", "question": "Total revenue this month?"},
        {"shop_id": "10", "question": "Top 5 products?"}
    ]

    async with httpx.AsyncClient() as client:
        tasks = [
            client.post("http://localhost:8000/api/ask", json=query)
            for query in queries
        ]
        responses = await asyncio.gather(*tasks)

    return [r.json() for r in responses]
```

## 🔍 Error Handling

### Common Error Responses

#### 1. Invalid Shop ID
```json
{
  "detail": "Shop ID must be a valid string"
}
```

#### 2. Database Connection Error
```json
{
  "shop_id": "10",
  "question": "How many orders?",
  "answer": "I couldn't connect to the database. Please try again later.",
  "query_type": "unknown",
  "processing_time": 0.5,
  "cached": false,
  "metadata": {"error": "Database connection failed"}
}
```

#### 3. LLM Service Unavailable
```json
{
  "answer": "I couldn't process your query using AI. Here's what I found with basic search: 174 orders",
  "query_type": "fallback",
  "processing_time": 2.1
}
```

#### 4. Timeout Error
```json
{
  "answer": "Your query is taking longer than expected. Please try a simpler question or contact support.",
  "metadata": {"error": "Query timeout after 30 seconds"}
}
```

### Error Handling Best Practices

```python
import httpx

async def robust_query(shop_id, question):
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:8000/api/ask",
                json={"shop_id": shop_id, "question": question}
            )
            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        return {"error": "Request timed out"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
```

## 📊 Monitoring & Analytics

### Response Time Tracking

```python
import time

def track_query_performance(query_func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = query_func(*args, **kwargs)
        end_time = time.time()

        print(f"Query processed in {end_time - start_time:.2f}s")
        print(f"Cache hit: {result.get('cached', False)}")
        print(f"Query type: {result.get('query_type', 'unknown')}")

        return result
    return wrapper
```

### Usage Analytics

```python
# Track query patterns
query_analytics = {
    "kpi_queries": 0,
    "llm_queries": 0,
    "analytical_queries": 0,
    "cache_hits": 0,
    "total_queries": 0
}

def log_query_stats(response):
    query_analytics["total_queries"] += 1
    query_analytics[f"{response['query_type']}_queries"] += 1

    if response.get("cached"):
        query_analytics["cache_hits"] += 1

    # Calculate cache hit rate
    hit_rate = query_analytics["cache_hits"] / query_analytics["total_queries"]
    print(f"Cache hit rate: {hit_rate:.2%}")
```

## 🔒 Security Considerations

### Input Validation

```python
import re

def validate_query(question: str) -> bool:
    # Length check
    if len(question) > 500:
        return False

    # Character whitelist
    if not re.match(r"^[a-zA-Z0-9\s\-.,?!']+$", question):
        return False

    # SQL injection patterns
    dangerous_patterns = ["DROP", "DELETE", "TRUNCATE", "UPDATE"]
    if any(pattern in question.upper() for pattern in dangerous_patterns):
        return False

    return True
```

### Rate Limiting

```python
from collections import defaultdict, deque
import time

class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients = defaultdict(deque)

    def is_allowed(self, client_id):
        now = time.time()
        client_requests = self.clients[client_id]

        # Remove old requests outside window
        while client_requests and client_requests[0] < now - self.window_seconds:
            client_requests.popleft()

        # Check if under limit
        if len(client_requests) < self.max_requests:
            client_requests.append(now)
            return True

        return False
```

## 🚀 Integration Examples

### Python Integration

```python
import asyncio
import httpx
from typing import Dict, Any

class EcomInsightsClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = httpx.AsyncClient()

    async def ask(self, shop_id: str, question: str, **kwargs) -> Dict[str, Any]:
        """Ask a natural language question about e-commerce data"""
        payload = {
            "shop_id": shop_id,
            "question": question,
            **kwargs
        }

        response = await self.session.post(
            f"{self.base_url}/api/ask",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        response = await self.session.get(f"{self.base_url}/health")
        return response.json()

    async def close(self):
        await self.session.aclose()

# Usage example
async def main():
    client = EcomInsightsClient()

    try:
        # Business intelligence queries
        orders = await client.ask("10", "How many orders this month?")
        revenue = await client.ask("10", "What's my total revenue?")
        customers = await client.ask("10", "Show me top customers")

        print(f"Orders: {orders['answer']}")
        print(f"Revenue: {revenue['answer']}")
        print(f"Customers: {customers['answer']}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript Integration

```javascript
class EcomInsightsClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }

    async ask(shopId, question, options = {}) {
        const response = await fetch(`${this.baseUrl}/api/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                shop_id: shopId,
                question: question,
                ...options
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/health`);
        return await response.json();
    }
}

// Usage example
const client = new EcomInsightsClient();

async function getBusinessMetrics() {
    try {
        const results = await Promise.all([
            client.ask('10', 'How many orders today?'),
            client.ask('10', 'What are my top products?'),
            client.ask('10', 'Show me recent customers')
        ]);

        results.forEach((result, index) => {
            console.log(`Query ${index + 1}: ${result.answer}`);
        });

    } catch (error) {
        console.error('Error fetching metrics:', error);
    }
}

getBusinessMetrics();
```

### cURL Scripts

```bash
#!/bin/bash
# business_dashboard.sh - Quick business metrics

SHOP_ID="10"
BASE_URL="http://localhost:8000"

echo "=== Daily Business Report ==="

# Orders today
ORDERS=$(curl -s -X POST "${BASE_URL}/api/ask" \
  -H "Content-Type: application/json" \
  -d "{\"shop_id\":\"${SHOP_ID}\",\"question\":\"How many orders today?\"}")

echo "Orders: $(echo $ORDERS | jq -r '.answer')"

# Revenue
REVENUE=$(curl -s -X POST "${BASE_URL}/api/ask" \
  -H "Content-Type: application/json" \
  -d "{\"shop_id\":\"${SHOP_ID}\",\"question\":\"Total revenue this month?\"}")

echo "Revenue: $(echo $REVENUE | jq -r '.answer')"

# Top products
PRODUCTS=$(curl -s -X POST "${BASE_URL}/api/ask" \
  -H "Content-Type: application/json" \
  -d "{\"shop_id\":\"${SHOP_ID}\",\"question\":\"What are my top selling products?\"}")

echo "Top Products: $(echo $PRODUCTS | jq -r '.answer')"

echo "=== Report Complete ==="
```

## 🎯 Best Practices

### 1. Query Design

**Good Queries:**
- "Show me orders from last week"
- "Which products are low in stock?"
- "Find customers who haven't ordered in 30 days"

**Better Queries:**
- "Show me orders from last week with total value over $100"
- "Which products have less than 10 units in stock?"
- "Find VIP customers (>$1000 total spent) who haven't ordered in 30 days"

### 2. Performance Optimization

```python
# Cache frequently asked questions
common_queries = [
    "How many orders today?",
    "What's my revenue this month?",
    "Show me top customers",
    "Which products are selling well?"
]

# Pre-warm cache
for query in common_queries:
    await client.ask(shop_id, query)
```

### 3. Error Recovery

```python
async def resilient_query(shop_id, question, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await client.ask(shop_id, question)
            if "error" not in result.get("metadata", {}):
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return {"error": "Max retries exceeded"}
```

### 4. Monitoring Integration

```python
import logging

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MonitoredClient(EcomInsightsClient):
    async def ask(self, shop_id: str, question: str, **kwargs):
        start_time = time.time()

        try:
            result = await super().ask(shop_id, question, **kwargs)

            # Log successful query
            logging.info(f"Query successful", extra={
                "shop_id": shop_id,
                "question": question[:50],
                "query_type": result.get("query_type"),
                "processing_time": result.get("processing_time"),
                "cached": result.get("cached"),
                "total_time": time.time() - start_time
            })

            return result

        except Exception as e:
            # Log failed query
            logging.error(f"Query failed", extra={
                "shop_id": shop_id,
                "question": question[:50],
                "error": str(e),
                "total_time": time.time() - start_time
            })
            raise
```

This API guide provides comprehensive examples and best practices for integrating with the E-Commerce Insights Server, ensuring optimal performance and reliability in production environments.