# System Architecture Documentation

## Overview

The E-Commerce Insights Server uses a sophisticated three-tier architecture to provide fast, accurate, and intelligent responses to natural language queries about e-commerce data.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Client Applications                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP/JSON
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Gateway                             │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │   Health    │ │     Ask      │ │     Documentation       │  │
│  │   Endpoint  │ │   Endpoint   │ │      Endpoint          │  │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Query Orchestrator                             │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │    Cache    │ │    Intent    │ │      Response           │  │
│  │   Manager   │ │ Classifier   │ │     Formatter           │  │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Tier 1    │ │   Tier 2    │ │   Tier 3    │
│     KPI     │ │     LLM     │ │     RAG     │
│  Templates  │ │ Generation  │ │ Analytics   │
│    <1sec    │ │   5-15sec   │ │  15-25sec   │
└─────────────┘ └─────────────┘ └─────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                  │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │  MongoDB    │ │    Redis     │ │      ChromaDB           │  │
│  │ Collections │ │    Cache     │ │   Vector Store          │  │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Query Orchestrator (`query_orchestrator.py`)

**Purpose**: Central coordination hub for all query processing

**Flow**:
```python
async def process_query(shop_id, question, context=None, use_cache=True):
    # 1. Check cache
    if cached_result := await cache.get(cache_key):
        return cached_result

    # 2. Classify intent
    intent_type, kpi_name, params = intent_classifier.classify(question)

    # 3. Route to appropriate handler
    if intent_type == IntentType.KPI:
        result = await _process_kpi_query(...)
    elif intent_type == IntentType.ANALYTICAL:
        result = await _process_analytical_query(...)
    else:
        result = await _process_llm_query(...)

    # 4. Format response and cache
    await cache.set(cache_key, result)
    return result
```

**Key Features**:
- Intelligent routing based on query complexity
- Automatic fallback mechanisms
- Performance monitoring and metrics
- Caching integration

### 2. Three-Tier Processing System

#### Tier 1: KPI Templates (`kpi_templates.py`)

**Purpose**: Lightning-fast responses for common business metrics

**Architecture**:
```python
TEMPLATE_REGISTRY = {
    "order_count": {
        "patterns": ["how many orders", "total orders", "order count"],
        "pipeline": lambda shop_id, params: [
            {"$match": {"shop_id": int(shop_id)}},
            {"$count": "count"}
        ],
        "collection": "order",
        "answer_template": "You have {count} orders"
    }
}
```

**Benefits**:
- Sub-second response times
- 100% accuracy for known patterns
- No AI processing overhead
- Predictable resource usage

#### Tier 2: LLM Generation (`ollama_service.py`)

**Purpose**: Dynamic MongoDB query generation for complex requests

**Architecture**:
```python
class OllamaService:
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
        self.client = httpx.AsyncClient()

    async def generate_query(self, question, shop_id, context):
        # Generate MongoDB aggregation pipeline
        response = await self.client.post("/api/generate", {
            "model": "mistral:7b-instruct",
            "system": self.system_prompt,
            "prompt": f"Shop ID: {shop_id}\nQuestion: {question}",
            "format": "json"
        })

        # Parse and validate response
        return self._parse_and_validate(response.json())
```

**Features**:
- Dynamic pipeline generation
- JSON format enforcement
- Robust error handling with fallbacks
- Security validation (prevents destructive operations)

#### Tier 3: RAG Analytics (`rag_service.py`)

**Purpose**: Context-aware analytical insights

**Architecture**:
```python
class RAGService:
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.vector_store = ChromaDB()

    async def search(self, query, shop_id, n_results=5):
        # Generate query embedding
        query_embedding = self.embedder.encode(query)

        # Search vector store
        results = self.vector_store.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"shop_id": shop_id}
        )

        return results
```

**Capabilities**:
- Semantic search over historical data
- Context-aware response generation
- Pattern recognition and trend analysis

### 3. Intelligent Response Formatting (`intelligent_formatter.py`)

**Purpose**: Transform raw data into human-readable business insights

**Architecture**:
```python
class IntelligentFormatter:
    def format_response(self, data, question, query_type):
        # Auto-detect data type
        if self._is_order_data(data):
            return self.format_orders_response(data, question)
        elif self._is_product_data(data):
            return self.format_products_response(data, question)
        else:
            return self.format_generic_response(data, question)

    def format_orders_response(self, data, question):
        if len(data) <= 5:
            return self._format_order_summary(data)
        else:
            return self._format_order_aggregate(data)
```

**Key Features**:
- Automatic data type detection
- Context-aware formatting
- Business metric calculations
- Scalable response strategies (summary vs. aggregate)

## Data Flow Architecture

### 1. Request Processing Pipeline

```
HTTP Request → Validation → Query Orchestrator
                ↓
            Cache Check → Hit? → Return Cached Response
                ↓ Miss
            Intent Classification
                ↓
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  KPI       LLM         RAG
Template  Generation  Analytics
    ↓           ↓           ↓
    └───────────┼───────────┘
                ▼
        MongoDB Execution
                ↓
      Response Formatting
                ↓
         Cache & Return
```

### 2. Database Architecture

#### MongoDB Collections

```javascript
// Primary collections
order: {
    id: ObjectId,
    shop_id: Number,        // KEY: Must be integer
    grand_total: Number,
    status: String,
    created_at: Date,
    // ... business fields
}

product: {
    id: ObjectId,
    shop_id: Number,        // KEY: Must be integer
    name: String,
    price: Number,
    stock_quantity: Number,
    // ... catalog fields
}

customer: {
    id: ObjectId,
    shop_id: Number,        // KEY: Must be integer
    first_name: String,
    last_name: String,
    email: String,
    // ... profile fields
}
```

#### Indexing Strategy

```javascript
// Performance indexes
db.order.createIndex({shop_id: 1, created_at: -1})    // Time-series queries
db.order.createIndex({shop_id: 1, status: 1})         // Status filtering
db.product.createIndex({shop_id: 1, status: 1})       // Active products
db.customer.createIndex({shop_id: 1})                 // Customer lookup
```

### 3. Caching Architecture

#### Redis Caching Strategy

```python
# Cache key pattern
cache_key = f"{shop_id}:{question_hash}"

# TTL strategy
TTL_MAPPING = {
    "real-time": 300,      # 5 minutes
    "hourly": 3600,        # 1 hour
    "daily": 86400,        # 24 hours
    "static": 604800       # 1 week
}

# Cache invalidation
async def invalidate_cache(shop_id, data_type):
    pattern = f"{shop_id}:*{data_type}*"
    await redis.delete_pattern(pattern)
```

#### Cache Hit Rate Optimization

- **Hot Queries**: Common KPIs cached for 1 hour
- **Cold Queries**: Complex LLM results cached for 24 hours
- **Analytical**: RAG insights cached for 1 week
- **Invalidation**: Smart cache busting on data updates

## Error Handling & Resilience

### 1. Fault Tolerance

```python
# Circuit breaker pattern
@circuit_breaker(failure_threshold=5, timeout=60)
async def call_ollama_service():
    # LLM service call with automatic fallback
    pass

# Retry with exponential backoff
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def execute_mongodb_query():
    # Database query with retry logic
    pass
```

### 2. Graceful Degradation

```python
# Service availability hierarchy
try:
    result = await kpi_service.process()
except ServiceUnavailable:
    try:
        result = await llm_service.process()
    except ServiceUnavailable:
        result = await fallback_service.process()
```

### 3. Input Validation & Security

```python
# Pipeline security validation
def _validate_pipeline(self, pipeline):
    dangerous_ops = ["$merge", "$out", "$function", "$accumulator"]
    for stage in pipeline:
        if any(op in stage for op in dangerous_ops):
            raise SecurityError("Dangerous operation detected")
    return True

# Input sanitization
def sanitize_input(query: str) -> str:
    # Remove potential injection patterns
    return re.sub(r'[^\w\s\-.,?!]', '', query)
```

## Performance Optimization

### 1. Query Optimization

- **Pipeline Optimization**: Minimize data transfer with early filtering
- **Projection**: Return only required fields
- **Indexing**: Strategic index placement for common access patterns
- **Aggregation**: Push computation to database level

### 2. Memory Management

```python
# Connection pooling
motor_client = AsyncIOMotorClient(
    uri,
    maxPoolSize=50,
    minPoolSize=10,
    maxIdleTimeMS=30000
)

# Model loading optimization
@lru_cache(maxsize=1)
def load_huggingface_model():
    return pipeline("text2text-generation", model="facebook/bart-base")
```

### 3. Concurrency Optimization

```python
# Async processing
async def process_multiple_queries(queries):
    tasks = [process_single_query(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## Monitoring & Observability

### 1. Metrics Collection

```python
# Performance metrics
@histogram_timer("query_processing_time")
async def process_query():
    # Processing logic with automatic timing
    pass

# Business metrics
@counter("successful_queries")
@counter("failed_queries")
async def execute_query():
    # Query execution with success/failure tracking
    pass
```

### 2. Health Checks

```python
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": await check_mongodb(),
            "ollama": await check_ollama(),
            "cache": await check_redis(),
            "formatter": check_huggingface()
        }
    }
```

### 3. Logging Strategy

```python
# Structured logging
logger.info("Query processed", extra={
    "shop_id": shop_id,
    "query_type": intent_type.value,
    "processing_time": elapsed_time,
    "cache_hit": was_cached,
    "query_hash": query_hash
})
```

## Security Considerations

### 1. Data Isolation

- **Shop-level isolation**: All queries automatically filtered by shop_id
- **Parameter binding**: Prevent injection through parameterized queries
- **Pipeline validation**: Block dangerous MongoDB operations

### 2. Rate Limiting

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_client_ip)

@app.post("/api/ask")
@limiter.limit("60/minute")
async def ask_endpoint():
    # Rate-limited endpoint
    pass
```

### 3. Input Validation

- Query length limits
- Character whitelisting
- SQL/NoSQL injection prevention
- Output sanitization

## Scalability Considerations

### 1. Horizontal Scaling

- **Stateless services**: All components can be horizontally scaled
- **Database sharding**: MongoDB sharding by shop_id
- **Load balancing**: Round-robin with health checks
- **Cache distribution**: Redis cluster for high availability

### 2. Vertical Scaling

- **Memory optimization**: Model quantization for lower memory usage
- **CPU optimization**: Batch processing for multiple queries
- **Storage optimization**: Compressed model storage

### 3. Auto-scaling Triggers

```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ecom-insights
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

This architecture provides a robust, scalable, and maintainable foundation for natural language e-commerce analytics with enterprise-grade performance and reliability.