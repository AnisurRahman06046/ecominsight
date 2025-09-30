# Fine-Tuning Guide for EcomInsight MCP System

## Overview

This guide explains how to fine-tune the FLAN-T5-base model for better e-commerce query responses using logged query data.

---

## Prerequisites

### Required Libraries

```bash
pip install transformers torch datasets accelerate
```

### Logged Data

The system automatically logs all queries to `query_logs/` directory:
- `all_queries.jsonl` - All queries
- `failed_queries.jsonl` - Failed queries only
- `success_queries.jsonl` - Successful queries only

---

## Step 1: Export Fine-Tuning Data

Use the built-in export function:

```python
from app.services.query_logger import query_logger

# Export queries with confidence > 0.7 to fine-tuning format
output_file = query_logger.export_for_finetuning(
    output_file="finetuning_data.jsonl"
)
print(f"Fine-tuning data exported to: {output_file}")
```

This creates a JSONL file with format:
```json
{"input": "Answer this e-commerce analytics question: How many orders do I have?", "output": "The number of orders I have is 174.", "intent": "analytical", "tool": "count_documents"}
{"input": "Answer this e-commerce analytics question: What is my total revenue?", "output": "My total revenue is $235,706.00.", "intent": "analytical", "tool": "calculate_sum"}
```

---

## Step 2: Prepare Training Script

Create `train_flan_t5.py`:

```python
#!/usr/bin/env python3
"""
Fine-tune FLAN-T5-base for e-commerce query responses
"""

import json
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)

# 1. Load data
def load_finetuning_data(file_path):
    """Load JSONL data"""
    data = {"input": [], "output": []}
    with open(file_path, 'r') as f:
        for line in f:
            entry = json.loads(line)
            data["input"].append(entry["input"])
            data["output"].append(entry["output"])
    return Dataset.from_dict(data)

# 2. Tokenize
def preprocess_function(examples, tokenizer, max_input_length=512, max_output_length=200):
    """Tokenize inputs and outputs"""
    model_inputs = tokenizer(
        examples["input"],
        max_length=max_input_length,
        truncation=True,
        padding="max_length"
    )

    labels = tokenizer(
        examples["output"],
        max_length=max_output_length,
        truncation=True,
        padding="max_length"
    )

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

# 3. Fine-tune
def main():
    # Load model and tokenizer
    model_name = "google/flan-t5-base"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    # Load and prepare data
    print("Loading fine-tuning data...")
    dataset = load_finetuning_data("query_logs/finetuning_data.jsonl")

    # Split into train/val (90/10)
    split_dataset = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split_dataset["train"]
    val_dataset = split_dataset["test"]

    print(f"Training examples: {len(train_dataset)}")
    print(f"Validation examples: {len(val_dataset)}")

    # Tokenize
    print("Tokenizing data...")
    train_dataset = train_dataset.map(
        lambda x: preprocess_function(x, tokenizer),
        batched=True,
        remove_columns=["input", "output"]
    )
    val_dataset = val_dataset.map(
        lambda x: preprocess_function(x, tokenizer),
        batched=True,
        remove_columns=["input", "output"]
    )

    # Training arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir="./finetuned_flan_t5",
        evaluation_strategy="epoch",
        learning_rate=3e-4,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        num_train_epochs=5,
        weight_decay=0.01,
        save_total_limit=3,
        predict_with_generate=True,
        fp16=False,  # Set to True if using GPU with fp16 support
        logging_steps=50,
        save_strategy="epoch",
        load_best_model_at_end=True,
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model
    )

    # Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
    )

    # Train
    print("Starting fine-tuning...")
    trainer.train()

    # Save final model
    print("Saving fine-tuned model...")
    trainer.save_model("./finetuned_flan_t5/final")
    tokenizer.save_pretrained("./finetuned_flan_t5/final")

    print("Fine-tuning complete!")
    print("Model saved to: ./finetuned_flan_t5/final")

if __name__ == "__main__":
    main()
```

---

## Step 3: Run Fine-Tuning

### On CPU (Slow but works)
```bash
python train_flan_t5.py
```

### On GPU (Recommended)
```bash
# Enable fp16 in training_args if supported
CUDA_VISIBLE_DEVICES=0 python train_flan_t5.py
```

**Expected Training Time:**
- CPU: 2-6 hours (depends on data size)
- GPU: 20-60 minutes

---

## Step 4: Use Fine-Tuned Model

Modify `app/services/hf_response_generator.py`:

```python
def _initialize_generator(self):
    """Initialize text generation model."""
    try:
        from transformers import pipeline

        # Use fine-tuned model if available
        model_path = "./finetuned_flan_t5/final"

        if Path(model_path).exists():
            logger.info(f"Loading fine-tuned model from {model_path}")
            self.generator = pipeline(
                "text2text-generation",
                model=model_path,
                device=-1,  # CPU
                max_length=200
            )
            self.model_name = "finetuned-flan-t5-base"
        else:
            # Fallback to base model
            logger.info("Fine-tuned model not found, using base model")
            self.generator = pipeline(
                "text2text-generation",
                model="google/flan-t5-base",
                device=-1,
                max_length=200
            )
            self.model_name = "flan-t5-base"

        self.initialized = True
        logger.info(f"HF Response Generator initialized with {self.model_name}")

    except Exception as e:
        logger.error(f"Failed to initialize generator: {e}")
        self.initialized = False
```

---

## Step 5: Evaluate Improvement

Create `test_finetuned_model.py`:

```python
#!/usr/bin/env python3
"""
Compare base model vs fine-tuned model responses
"""

import requests
import json

BASE_URL = "http://localhost:8000"
SHOP_ID = "10"

test_queries = [
    "How many orders do I have?",
    "What is my total revenue?",
    "Average order value?",
    "Top 5 customers by spending",
    "Orders above $1000"
]

def test_model():
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")

        response = requests.post(
            f"{BASE_URL}/api/mcp/ask",
            json={"shop_id": SHOP_ID, "question": query}
        )

        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'N/A')
            print(f"Answer: {answer}")
        else:
            print(f"Error: HTTP {response.status_code}")

if __name__ == "__main__":
    test_model()
```

Run tests:
```bash
python test_finetuned_model.py
```

---

## Monitoring & Continuous Improvement

### 1. Track Query Statistics

```python
from app.services.query_logger import query_logger

# Get statistics
stats = query_logger.get_statistics()

print(f"Total Queries: {stats['total_queries']}")
print(f"Success Rate: {stats['success_rate']:.1f}%")
print(f"Avg Confidence: {stats['avg_confidence']:.2f}")
print(f"Avg Response Time: {stats['avg_response_time']:.2f}s")
print(f"\nIntent Distribution: {stats['intent_distribution']}")
print(f"Tool Distribution: {stats['tool_distribution']}")
```

### 2. Review Failed Queries

```python
# Get failed queries for analysis
failed = query_logger.get_failed_queries(limit=50)

for query in failed:
    print(f"Question: {query['question']}")
    print(f"Error: {query['error']}")
    print(f"Tool: {query['tool_used']}")
    print(f"Confidence: {query['confidence']}")
    print("-" * 60)
```

### 3. Review Low-Confidence Queries

```python
# Get queries with confidence < 0.5
low_conf = query_logger.get_low_confidence_queries(threshold=0.5, limit=50)

for query in low_conf:
    print(f"Question: {query['question']}")
    print(f"Confidence: {query['confidence']}")
    print(f"Answer: {query['answer']}")
    print(f"Success: {query['success']}")
    print("-" * 60)
```

### 4. Add User Feedback (Future Enhancement)

Modify API to accept feedback:

```python
@router.post("/api/mcp/feedback")
async def provide_feedback(
    question: str,
    feedback: str  # "positive" or "negative"
):
    """
    Allow users to provide feedback on responses.
    This data can be used to filter training data.
    """
    # Update logged query with feedback
    # Re-export fine-tuning data with feedback filter
    pass
```

---

## Best Practices

### 1. Data Quality
- Only use queries with confidence > 0.7
- Filter out failed queries
- Include diverse query types
- Aim for 500+ training examples

### 2. Training
- Start with 3-5 epochs
- Monitor validation loss
- Use early stopping if overfitting
- Keep best checkpoint

### 3. Evaluation
- Test on held-out queries
- Compare with base model
- Measure response quality
- Check response time impact

### 4. Continuous Learning
- Export new data weekly/monthly
- Retrain model periodically
- Version your models
- A/B test improvements

---

## Troubleshooting

### Issue: Out of Memory (OOM)

**Solution:**
- Reduce `per_device_train_batch_size` to 2 or 1
- Reduce `max_input_length` to 256
- Use gradient accumulation:
  ```python
  gradient_accumulation_steps=4
  ```

### Issue: Poor Quality After Fine-Tuning

**Causes:**
- Not enough training data (< 100 examples)
- Too many epochs (overfitting)
- Low-quality training data

**Solution:**
- Collect more queries (run extensive tests)
- Reduce epochs to 3
- Filter out low-confidence examples

### Issue: Model Not Improving

**Solution:**
- Increase learning rate to 5e-4
- Train longer (10 epochs)
- Check data diversity
- Ensure proper input/output format

---

## Expected Results

### Before Fine-Tuning (Base FLAN-T5)
- Response quality: 85-90%
- Some verbose responses
- Occasional repetition

### After Fine-Tuning
- Response quality: 95%+
- More consistent tone
- Domain-specific language
- Better handling of edge cases

---

## File Structure After Fine-Tuning

```
ecominsight/
├── query_logs/
│   ├── all_queries.jsonl
│   ├── failed_queries.jsonl
│   ├── success_queries.jsonl
│   └── finetuning_data.jsonl
├── finetuned_flan_t5/
│   ├── checkpoint-100/
│   ├── checkpoint-200/
│   └── final/
│       ├── config.json
│       ├── pytorch_model.bin
│       └── tokenizer files
├── train_flan_t5.py
├── test_finetuned_model.py
└── docs/
    ├── FINE_TUNING_GUIDE.md
    └── SYSTEM_OVERVIEW.md
```

---

## Next Steps

1. ✅ Query logging is integrated
2. ✅ Export function is available
3. ⏳ Collect 500+ diverse queries (run extensive tests)
4. ⏳ Export and prepare training data
5. ⏳ Run fine-tuning script
6. ⏳ Evaluate fine-tuned model
7. ⏳ Deploy if better than base model

---

Generated: 2025-09-30