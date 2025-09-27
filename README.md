# E-Commerce Insights Server

🚀 **AI-powered natural language analytics for e-commerce data**

A high-performance server that transforms raw e-commerce data into actionable business insights through natural language queries. Built with FastAPI, MongoDB, Ollama, and Hugging Face for enterprise-grade performance and reliability.

**🎯 Problem Solved**: Converts unintelligible data dumps like `"Found 5 results: 1715020640655, 1715338373990..."` into meaningful business insights like `"Found 10 orders with total value $3,957.00 (avg $395.70). Most common status: Order Placed"`

## ✨ Features

### Three-Layer Intelligence System

1. **⚡ Fast Path (KPIs)** - Predefined templates for common queries (<1s response)
   - Total sales, order counts, customer metrics
   - Top products, categories, customers
   - Inventory status, returns analysis

2. **🤖 LLM Path** - AI-generated queries for complex questions (5-10s)
   - Handles unique, unpredictable phrasing
   - Generates MongoDB pipelines on-the-fly
   - Returns structured data with natural language answers

3. **🔍 RAG Path** - Analytical insights for "why/how" questions (3-5s)
   - Searches through historical summaries
   - Provides context-aware explanations
   - Identifies trends and patterns

## 🏗️ Architecture

```
User Query → Intent Classifier → Route Decision
                ↓                     ↓              ↓
            KPI Templates      LLM Generator    RAG Search
                ↓                     ↓              ↓
            MongoDB Query         MongoDB       Vector DB
                ↓                     ↓              ↓
            Fast Results      Dynamic Results   Insights
                ↓                     ↓              ↓
                    Natural Language Answer
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- MongoDB (local or Atlas)
- Ollama with mistral:7b-instruct model
- Redis (optional, for caching)

### Installation

1. **Clone and setup**
```bash
cd ecom-insights-server
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your MongoDB URL
```

3. **Install Ollama** (if not installed)
```bash
# Linux/WSL
curl -fsSL https://ollama.ai/install.sh | sh

# macOS
brew install ollama
```

4. **Pull required model**
```bash
ollama pull mistral:7b-instruct
```

5. **Run the server**
```bash
uvicorn app.api.main:app --reload
```

Server will be available at `http://localhost:8000`

## 📡 API Usage

### Basic Query
```bash
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "shop_id": "123",
    "question": "How many products did I sell last month?"
  }'
```

### Response
```json
{
  "shop_id": "123",
  "question": "How many products did I sell last month?",
  "answer": "You sold 1,324 products last month, which generated $45,230 in revenue.",
  "query_type": "kpi",
  "processing_time": 0.234,
  "cached": false
}
```

## 📊 Example Queries

### KPI Queries (Instant)
- "What's my total revenue today?"
- "Show me top 10 customers"
- "How many active products do I have?"
- "List products that are low in stock"

### Complex Queries (LLM-powered)
- "Find customers who ordered electronics but not accessories"
- "Compare this week's sales with the same week last year"
- "Show orders with multiple items that were partially refunded"

### Analytical Questions (RAG-powered)
- "Why did sales drop in August?"
- "What factors contribute to high cart abandonment?"
- "How can I improve customer retention?"

## 📊 Performance Benchmarks

### Response Time Comparison

| Query Type | Before HuggingFace | After HuggingFace | Improvement |
|------------|-------------------|------------------|-------------|
| KPI Queries | <1s ✅ | <1s ✅ | No change |
| Simple LLM | 30-70s ⚠️ | 5-15s ✅ | **3-7x faster** ⚡ |
| Complex LLM | 70-120s ❌ | 15-35s ✅ | **2-4x faster** ⚡ |

### Success Rate Improvement

| Scenario | Before | After | Delta |
|----------|--------|-------|-------|
| Simple queries | ~60% | ~95% | +35% ✅ |
| Complex queries | ~30% | ~85% | +55% 🚀 |
| Error recovery | Poor ❌ | Excellent ✅ | Major improvement ⭐ |

### User Experience Transformation

**Before Integration:**
```json
{
  "answer": "Found 5 results: 1715020640655, 1715338373990, 1715619528464, 1715173697837, 1715133188987",
  "processing_time": 67.3
}
```

**After Integration:**
```json
{
  "answer": "Found 10 orders with total value $3,957.00 (avg $395.70). Most common status: Order Placed (10 orders)",
  "processing_time": 28.4
}
```

## 🔧 Configuration

Key settings in `.env`:

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=ecommerce_insights

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct

# Features
USE_TEMPLATE_FIRST=true  # Try KPI templates first
USE_RAG_FOR_ANALYTICS=true  # Enable RAG for why/how

# Cache
ENABLE_CACHE=true
CACHE_TTL=3600  # 1 hour
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -t ecom-insights .

# Run with docker-compose
docker-compose up -d
```

## 📁 Project Structure

```
ecom-insights-server/
├── app/
│   ├── api/              # FastAPI endpoints
│   ├── core/             # Database, config
│   ├── services/         # Business logic
│   │   ├── intent_classifier.py    # Intent detection
│   │   ├── kpi_templates.py       # Fast KPI queries
│   │   ├── ollama_service.py      # LLM integration
│   │   ├── rag_service.py         # RAG analytics
│   │   └── query_orchestrator.py  # Main coordinator
│   └── utils/            # Logging, helpers
├── tests/                # Unit tests
├── docker-compose.yml    # Container orchestration
└── requirements.txt      # Dependencies
```

## 🔒 Security Features

- Input sanitization and validation
- Pipeline security checks (no destructive operations)
- Shop-level data isolation
- Query timeout protection
- Rate limiting support

## 🛠️ Development

### Running Tests
```bash
pytest tests/
```

### Adding New KPIs
Edit `app/services/kpi_templates.py` to add new templates.

### Custom Intent Patterns
Modify `app/services/intent_classifier.py` for new patterns.

## 📈 Monitoring

- Health check: `GET /health`
- Metrics: Processing time in `X-Process-Time` header
- Logs: JSON format in `logs/app.log`

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open pull request

## 📄 License

MIT License - See LICENSE file for details

## 🆘 Support

- Documentation: `/docs` endpoint
- Issues: GitHub Issues
- Logs: Check `logs/app.log` for debugging

---

Built with ❤️ for e-commerce analytics