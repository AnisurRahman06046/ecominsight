# 🤗 Hugging Face Integration Guide

## Current vs Hugging Face Comparison

| Feature | Current (Ollama) | With Hugging Face |
|---------|------------------|-------------------|
| KPI Queries | <1s ✅ | <1s ✅ |
| Simple LLM | 30-70s ⚠️ | 5-10s ✅ |
| Complex Queries | Sometimes fails ❌ | More reliable ✅ |
| Intent Classification | Pattern matching | ML-based classification |
| Setup Complexity | Simple | Moderate |
| Resource Usage | 4GB | 6-8GB |

## What to Add

### 1. Intent Classification (facebook/bart-large-mnli)
- Better "why/how/analyze" detection
- Multi-language support
- Confidence scores

### 2. Query Generation (CodeT5/text-to-code models)
- Better MongoDB syntax generation
- More reliable JSON output
- Code-specific training

### 3. Embeddings (sentence-transformers)
- RAG functionality for analytical questions
- Vector similarity search
- Context understanding

## Implementation Steps

### Step 1: Install Dependencies
```bash
pip install transformers torch sentence-transformers
```

### Step 2: Replace Intent Classifier
```python
# Use app/services/intent_classifier_ml.py
from transformers import pipeline
classifier = pipeline("zero-shot-classification",
                     model="facebook/bart-large-mnli")
```

### Step 3: Add Query Generation Model
```python
from transformers import CodeT5ForConditionalGeneration
model = CodeT5ForConditionalGeneration.from_pretrained("salesforce/codet5-small")
```

### Step 4: Enable RAG System
```python
from sentence_transformers import SentenceTransformer
embedder = SentenceTransformer("all-MiniLM-L6-v2")
```

## Expected Improvements

### Before (Current)
```
User: "Show me orders from last week with more than 3 items"
↓ (70 seconds, sometimes fails)
Answer: "I couldn't process your query. Error: Invalid syntax..."
```

### After (Hugging Face)
```
User: "Show me orders from last week with more than 3 items"
↓ (8 seconds, more reliable)
Answer: "Found 12 orders from last week with more than 3 items"
```

## Resource Requirements

- **RAM**: +2-4GB (total 6-8GB)
- **Storage**: +3-5GB for models
- **CPU**: Will use more CPU for inference

## Migration Plan

### Phase 1: Intent Classification
- Replace pattern matching with BART
- Test accuracy improvement

### Phase 2: Query Generation
- Add CodeT5 model for MongoDB generation
- Compare with Ollama results

### Phase 3: RAG Analytics
- Enable sentence transformers
- Add analytical question support

## Quick Test

Want to test Hugging Face models? Run:

```bash
pip install transformers torch
python -c "
from transformers import pipeline
classifier = pipeline('zero-shot-classification', model='facebook/bart-large-mnli')
result = classifier('How many products do I have?', ['data query', 'analytical question', 'general question'])
print('Intent:', result['labels'][0], 'Confidence:', result['scores'][0])
"
```

## Decision Factors

**Stay with Ollama if:**
- Current performance is acceptable
- You want to keep things simple
- Resource usage is a concern

**Upgrade to Hugging Face if:**
- You need faster LLM queries
- You want better accuracy for complex queries
- You want to enable analytical/RAG features
- Performance and reliability are priorities

## Bottom Line

Your current system **works great** for:
- ✅ KPI queries (instant)
- ✅ Simple LLM queries (works but slow)

Hugging Face would make it **production-ready** with:
- 🚀 3-7x faster LLM queries
- 📈 Better reliability for complex questions
- 🧠 Smarter intent understanding