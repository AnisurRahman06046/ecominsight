# Query Logging & Fine-Tuning System

## Overview

The EcomInsight MCP system now includes comprehensive query logging and fine-tuning capabilities to continuously improve response quality.

---

## Components Added

### 1. Query Logger (`app/services/query_logger.py`)

**Purpose**: Track all queries, responses, and failures for analysis and model improvement.

**Features**:
- ✅ Logs all queries to JSONL files
- ✅ Separate logs for all/success/failed queries
- ✅ Tracks metadata (tool, intent, confidence, response time, errors)
- ✅ Get failed queries for debugging
- ✅ Get low-confidence queries for review
- ✅ Generate statistics (success rate, avg confidence, tool distribution)
- ✅ Export data in fine-tuning format

**Log Files** (auto-created in `query_logs/`):
```
query_logs/
├── all_queries.jsonl          # All queries
├── failed_queries.jsonl       # Failed queries only
├── success_queries.jsonl      # Successful queries only
└── finetuning_data.jsonl      # Exported for training (created on demand)
```

**Log Entry Format**:
```json
{
  "timestamp": "2025-09-30T12:34:56.789012",
  "question": "How many orders do I have?",
  "shop_id": 10,
  "answer": "The number of orders I have is 174.",
  "tool_used": "count_documents",
  "intent": "analytical",
  "confidence": 0.9,
  "success": true,
  "response_time": 1.45,
  "error": null,
  "has_data": true,
  "user_feedback": null
}
```

### 2. Integrated Logging (`app/services/llm_mcp_orchestrator.py`)

**Changes Made**:
- Added `import time` for response time tracking
- Added `from app.services.query_logger import query_logger`
- Added timing at start of `process_query()`: `start_time = time.time()`
- Added logging for:
  - ✅ Successful queries (with full metadata)
  - ✅ Failed queries (with error messages)
  - ✅ Exceptions (with stack trace info)

**Logged Automatically**:
- Every query to `/api/mcp/ask`
- Success/failure status
- Tool used and parameters
- Intent and confidence
- Response time
- Error messages (if failed)

### 3. Analysis Script (`scripts/analyze_query_logs.py`)

**Purpose**: Analyze logged queries and generate insights.

**Features**:
- 📊 Overall statistics (total, success rate, avg confidence, avg time)
- ❌ Failed queries analysis (grouped by error type)
- ⚠️ Low-confidence queries review
- ⏱️ Response time distribution
- 📈 Confidence distribution
- 💡 Recommendations for improvement
- 📤 Export fine-tuning data

**Usage**:
```bash
python scripts/analyze_query_logs.py
```

**Sample Output**:
```
==================================================================
OVERALL STATISTICS
==================================================================

Total Queries: 100
Failed Queries: 0
Success Rate: 100.0%
Avg Confidence: 0.87
Avg Response Time: 3.84s

Intent Distribution:
  analytical: 100

Tool Distribution:
  count_documents: 30
  calculate_sum: 20
  calculate_average: 20
  get_top_customers_by_spending: 15
  ...

==================================================================
RECOMMENDATIONS
==================================================================

✓ Success rate is excellent (100.0%)
✓ Average confidence is good (0.87)
✓ Sufficient queries for fine-tuning (100)

Next Steps:
→ Ready to fine-tune! Run: python train_flan_t5.py
```

### 4. Fine-Tuning Guide (`docs/FINE_TUNING_GUIDE.md`)

**Purpose**: Complete guide for fine-tuning FLAN-T5-base on collected query data.

**Includes**:
- Prerequisites and setup
- Step-by-step fine-tuning instructions
- Training script (`train_flan_t5.py`)
- Evaluation script
- Best practices
- Troubleshooting guide

---

## How It Works

### 1. Automatic Logging

Every query to `/api/mcp/ask` is automatically logged:

```
User Query → LLM MCP Orchestrator
           ↓
       [Log Start]
           ↓
   Intent Classification
           ↓
   Tool Selection
           ↓
   Tool Execution
           ↓
   Response Generation
           ↓
  [Log End - Success/Failure]
           ↓
   Return to User
```

### 2. Log Analysis

Run analysis script periodically:

```bash
python scripts/analyze_query_logs.py
```

This shows:
- Overall system health
- Failed queries to debug
- Low-confidence queries to improve
- Recommendations for next steps

### 3. Data Export

Export queries for fine-tuning:

```python
from app.services.query_logger import query_logger

# Export successful queries with confidence > 0.7
output_file = query_logger.export_for_finetuning()
print(f"Exported to: {output_file}")
```

**Export Format** (JSONL):
```json
{"input": "Answer this e-commerce analytics question: How many orders do I have?", "output": "The number of orders I have is 174.", "intent": "analytical", "tool": "count_documents"}
{"input": "Answer this e-commerce analytics question: What is my total revenue?", "output": "My total revenue is $235,706.00.", "intent": "analytical", "tool": "calculate_sum"}
```

### 4. Model Fine-Tuning

Use exported data to fine-tune FLAN-T5:

```bash
# Create training script (see FINE_TUNING_GUIDE.md)
python train_flan_t5.py
```

**Expected Improvement**:
- Before: 85-90% natural responses
- After: 95%+ natural responses
- More consistent tone
- Better domain knowledge

### 5. Deploy Fine-Tuned Model

Modify `hf_response_generator.py` to use fine-tuned model:

```python
# Load fine-tuned model instead of base
model_path = "./finetuned_flan_t5/final"
self.generator = pipeline("text2text-generation", model=model_path)
```

---

## Usage Examples

### View Query Statistics

```python
from app.services.query_logger import query_logger

stats = query_logger.get_statistics()
print(f"Success Rate: {stats['success_rate']:.1f}%")
print(f"Avg Confidence: {stats['avg_confidence']:.2f}")
print(f"Tool Distribution: {stats['tool_distribution']}")
```

### Review Failed Queries

```python
failed = query_logger.get_failed_queries(limit=50)

for query in failed:
    print(f"Q: {query['question']}")
    print(f"Error: {query['error']}")
    print(f"Tool: {query['tool_used']}")
    print("-" * 60)
```

### Review Low-Confidence Queries

```python
low_conf = query_logger.get_low_confidence_queries(threshold=0.5, limit=50)

for query in low_conf:
    print(f"Q: {query['question']}")
    print(f"Confidence: {query['confidence']:.2f}")
    print(f"Success: {query['success']}")
    print(f"Answer: {query['answer']}")
    print("-" * 60)
```

### Export Training Data

```python
# Export all successful queries with confidence > 0.7
output_file = query_logger.export_for_finetuning(
    output_file="finetuning_data.jsonl"
)

print(f"Exported to: {output_file}")

# Count examples
with open(output_file, 'r') as f:
    count = sum(1 for _ in f)
print(f"Training examples: {count}")
```

---

## Workflow for Continuous Improvement

### Week 1: Data Collection
```bash
# Run extensive tests to collect diverse queries
python tests/extensive_test.py

# Analyze results
python scripts/analyze_query_logs.py
```

**Target**: 500+ successful queries

### Week 2: Analysis & Debugging
```bash
# Review failed queries
python scripts/analyze_query_logs.py

# Fix issues in code
# - Improve keyword matching
# - Fix tool parameters
# - Handle edge cases
```

**Target**: 95%+ success rate

### Week 3: Fine-Tuning
```bash
# Export training data
python scripts/analyze_query_logs.py
# Select 'y' to export

# Fine-tune model
python train_flan_t5.py
```

**Target**: Better response quality

### Week 4: Evaluation & Deployment
```bash
# Test fine-tuned model
python test_finetuned_model.py

# Compare with base model
# If better, deploy fine-tuned model
```

**Target**: 95%+ natural responses

### Ongoing: Monitor & Iterate
```bash
# Weekly: Check statistics
python scripts/analyze_query_logs.py

# Monthly: Retrain with new data
python train_flan_t5.py

# Quarterly: A/B test improvements
```

---

## Benefits

### 1. Debugging
- Quickly identify failed queries
- Understand error patterns
- Fix issues systematically

### 2. Monitoring
- Track success rate over time
- Monitor response quality
- Detect performance regressions

### 3. Model Improvement
- Collect real-world training data
- Fine-tune on domain-specific queries
- Continuously improve responses

### 4. User Feedback (Future)
- Add thumbs up/down buttons
- Filter training data by feedback
- Focus on user-approved responses

---

## File Structure

```
ecominsight/
├── app/
│   └── services/
│       ├── query_logger.py              # NEW: Query logging
│       └── llm_mcp_orchestrator.py      # MODIFIED: Added logging
├── query_logs/                          # NEW: Auto-created
│   ├── all_queries.jsonl
│   ├── failed_queries.jsonl
│   ├── success_queries.jsonl
│   └── finetuning_data.jsonl
├── scripts/
│   └── analyze_query_logs.py            # NEW: Analysis script
├── docs/
│   ├── FINE_TUNING_GUIDE.md             # NEW: Fine-tuning guide
│   ├── LOGGING_AND_FINETUNING.md        # NEW: This file
│   └── SYSTEM_OVERVIEW.md               # Existing
└── tests/
    └── extensive_test.py                # Existing
```

---

## Next Steps

### Immediate (Ready to Use)
1. ✅ Query logging is active
2. ✅ All queries are being logged
3. ✅ Analysis script is ready
4. ✅ Fine-tuning guide is complete

### Short-Term (This Week)
1. ⏳ Run extensive tests to collect 500+ queries
2. ⏳ Analyze logs and fix any issues
3. ⏳ Export training data

### Medium-Term (Next Month)
1. ⏳ Fine-tune FLAN-T5-base
2. ⏳ Evaluate fine-tuned model
3. ⏳ Deploy if improvement is significant

### Long-Term (Future)
1. ⏳ Add user feedback mechanism
2. ⏳ Implement A/B testing
3. ⏳ Automate retraining pipeline
4. ⏳ Add dashboard for monitoring

---

## Monitoring Dashboard (Future Enhancement)

Potential features for a monitoring dashboard:

```python
# Dashboard metrics
- Success rate over time (line chart)
- Tool usage distribution (bar chart)
- Response time distribution (histogram)
- Confidence distribution (histogram)
- Failed queries timeline (line chart)
- Top error types (pie chart)
- Low-confidence queries (table)
- Query volume by hour/day (line chart)
```

---

## Summary

The logging and fine-tuning system is now **fully integrated** and ready to use:

1. ✅ **Query Logger**: Tracks all queries automatically
2. ✅ **Integrated Logging**: Added to orchestrator
3. ✅ **Analysis Script**: Ready to analyze logs
4. ✅ **Fine-Tuning Guide**: Complete documentation
5. ✅ **Export Function**: Ready to generate training data

**What to do next**:
1. Run extensive tests to collect queries
2. Analyze logs periodically
3. Export and fine-tune when ready
4. Monitor improvements over time

---

Generated: 2025-09-30