# 🧪 Testing Guide - Ecommerce Insights Server

## Quick Start Testing (5 minutes)

### 1️⃣ Install and Setup

```bash
# Navigate to project
cd ecom-insights-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (simplified)
pip install fastapi uvicorn motor pymongo httpx ollama redis

# Copy environment file
cp .env.example .env
```

### 2️⃣ Start Required Services

**Option A: Using Docker (MongoDB + Redis)**
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
docker run -d -p 6379:6379 --name redis redis:latest
```

**Option B: Using existing MongoDB**
Edit `.env` and set your MongoDB URL:
```
MONGODB_URL=mongodb://localhost:27017
```

**Start Ollama** (required)
```bash
# In a separate terminal
ollama serve

# Pull the model if you don't have it
ollama pull mistral:7b-instruct
```

### 3️⃣ Load Sample Data

```bash
# Load test data into MongoDB
python load_sample_data.py
```

This creates:
- 3 test shops (IDs: 123, 456, 789)
- 150 products
- 300 customers
- ~4000 orders
- Inventory records
- Sample returns

### 4️⃣ Start the Server

```bash
# Using the run script
./run.sh

# Or manually
uvicorn app.api.main:app --reload
```

Server runs at: `http://localhost:8000`

### 5️⃣ Run Tests

**Automated Testing:**
```bash
python test_server.py
```

**Manual Testing with curl:**

```bash
# Health check
curl http://localhost:8000/health

# Test KPI query (fast)
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "How many orders do I have?"}'

# Test complex query (LLM)
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "Show me orders from last week with more than 3 items"}'

# Test analytical query (RAG)
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "Why are my sales trending down?"}'
```

## 📊 Test Scenarios

### Test 1: KPI Queries (Should be <1s)
These use predefined templates - super fast!

```python
questions = [
    "How many orders do I have?",
    "What's my total revenue today?",
    "Show me top 5 customers",
    "How many active products?",
    "What products are low in stock?",
    "Average order value this month?",
    "How many customers do I have?",
    "Total sales yesterday?",
    "Show me sales by category"
]
```

### Test 2: Cache Testing
Run the same query twice - second should be instant:

```bash
# First call (processes query)
time curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "Total revenue this week?"}'

# Second call (from cache - should be <100ms)
time curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "Total revenue this week?"}'
```

### Test 3: Complex Queries (LLM - 5-10s)
These require AI to generate MongoDB pipelines:

```python
questions = [
    "Find orders with electronics that cost more than $100",
    "Customers who ordered multiple times this month",
    "Products with sales but no inventory",
    "Orders from new customers in the last 7 days"
]
```

### Test 4: Analytical Queries (RAG - 3-5s)
These search through insights and provide analysis:

```python
questions = [
    "Why did sales drop last month?",
    "How can I improve conversion rates?",
    "What factors affect customer retention?",
    "Explain the sales pattern for electronics"
]
```

## 🔍 Using the Interactive Docs

Visit `http://localhost:8000/docs` for interactive API documentation where you can:
- Test all endpoints
- See request/response schemas
- Try different queries

## 📈 Performance Benchmarks

Expected response times:

| Query Type | Target Time | Actual (depends on hardware) |
|------------|------------|-------------------------------|
| Cached | <100ms | ✅ Instant |
| KPI Template | <1s | ✅ 200-500ms |
| LLM Query | <10s | ⚡ 5-10s |
| RAG Query | <5s | ⚡ 3-5s |

## 🐛 Troubleshooting

### "Ollama not found"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### "MongoDB connection failed"
```bash
# Check MongoDB is running
mongosh --eval "db.adminCommand('ping')"

# Or use Docker
docker run -d -p 27017:27017 mongo:latest
```

### "No data returned"
```bash
# Load sample data
python load_sample_data.py

# Verify data exists
mongosh ecommerce_insights --eval "db.orders.countDocuments({})"
```

### "Slow responses"
- First query is always slower (model loading)
- Ensure Ollama has enough RAM (4GB+ recommended)
- Check if caching is enabled in `.env`

## 🎯 Testing Checklist

- [ ] Server starts without errors
- [ ] Health endpoint returns healthy status
- [ ] Sample data loaded successfully
- [ ] KPI queries return in <1s
- [ ] Cache works (second query is instant)
- [ ] LLM queries work for complex questions
- [ ] RAG provides analytical insights
- [ ] Different shop_ids return different data
- [ ] API docs accessible at /docs

## 💡 Tips

1. **First Run**: The first query might be slow as models load
2. **Shop IDs**: Use 123, 456, or 789 (from sample data)
3. **Monitoring**: Check response time in `X-Process-Time` header
4. **Logs**: View detailed logs in terminal where server is running

## 📚 Example Test Session

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start server
cd ecom-insights-server
./run.sh

# Terminal 3: Run tests
python load_sample_data.py
python test_server.py

# Or test manually
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "123", "question": "What are my best selling products?"}'
```

Ready to test! 🚀