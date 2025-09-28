# Intent Classification - How It Works

## Overview

Both systems use **rule-based pattern matching** with regular expressions (regex). Neither system uses ML models for intent detection - they're both deterministic and fast.

---

## Example: "How many categories do I have?"

Let's trace how each system classifies this question:

---

## 🆕 NEW SYSTEM (Function Calling) - `intent_router.py`

### Step-by-Step Flow:

```python
question = "how many categories do i have?"
question_lower = question.lower().strip()
# Result: "how many categories do i have?"
```

### 1. Loop through all intent patterns:

```python
Intent.CATEGORY_COUNT patterns:
  ✓ r"how many categor"     # MATCHES!
  - r"number of categor"
  - r"category count"
  - r"total categor"
  - r"count.*categor"
```

### 2. Match found! Extract parameters:

```python
# Check for time period
re.search(r"(today|yesterday|this week...)", question_lower)
# No match → params = {}

# Check for limit
re.search(r"top (\d+)", question_lower)
# No match → params = {}

# Check for status
re.search(r"(pending|completed|cancelled...)", question_lower)
# No match → params = {}

# Final params = {}
```

### 3. Return result:

```python
return (Intent.CATEGORY_COUNT, {})
```

### ✅ Result: `category_count` with no extra params

---

## 🔴 OLD SYSTEM (LLM Generation) - `intent_classifier.py`

### Step-by-Step Flow:

```python
question = "how many categories do i have?"
question_lower = question.lower()
# Result: "how many categories do i have?"
```

### 1. Check if conversational:

```python
patterns = [
    r"^(hi|hello|hey|greetings)",
    r"how are you",
    r"what's up"
]

# No match → Not conversational
```

### 2. Check if analytical:

```python
analytical_keywords = [
    "why", "how", "explain", "reason", "cause",
    "trend", "pattern", "analyze", "compare"
]

# Check: does question contain "how"?
if f" how " in f" {question_lower} ":  # TRUE!
    return IntentType.ANALYTICAL
```

### ❌ Result: `analytical` (WRONG!)

**Why it failed:**
- The pattern `" how "` matches "**how** many categories"
- It stops checking and returns `ANALYTICAL` immediately
- Never reaches the KPI pattern matching for categories
- This is a **logic bug** in the old system

---

## Side-by-Side Comparison

| Question | New System | Old System | Winner |
|----------|-----------|-----------|---------|
| "how many categories do i have?" | `category_count` ✅ | `analytical` ❌ | **NEW** |
| "tell me how many categories do i have?" | `category_count` ✅ | `analytical` ❌ | **NEW** |
| "number of categories?" | `category_count` ✅ | Would work ✅ | **TIE** |
| "category count" | `category_count` ✅ | Would work ✅ | **TIE** |

---

## Why New System is Better

### 1. **Better Pattern Ordering**

**Old System:**
```python
1. Check conversational
2. Check analytical (too broad - catches "how")
3. Check KPI patterns (never reached!)
```

**New System:**
```python
1. Check all specific intents (including category_count)
2. Return UNKNOWN if no match
```

### 2. **More Specific Patterns**

**Old System:**
- Has category patterns but never reaches them due to "how" keyword

**New System:**
```python
Intent.CATEGORY_COUNT: [
    r"how many categor",      # Catches "how many categories"
    r"number of categor",     # Catches "number of categories"
    r"category count",        # Catches "category count"
    r"total categor",         # Catches "total categories"
    r"count.*categor"         # Catches "count my categories"
]
```

### 3. **No Overly Broad Keywords**

**Old System Problem:**
```python
analytical_keywords = ["how", "why", "explain", ...]

# This catches WAY too many questions:
"how many products"     → analytical ❌ (should be product_count)
"how many orders"       → analytical ❌ (should be order_count)
"how many categories"   → analytical ❌ (should be category_count)
"how much revenue"      → analytical ❌ (should be total_revenue)
```

**New System Solution:**
- No broad keywords
- Only specific patterns for each intent
- Returns `UNKNOWN` if no match (better than wrong match)

---

## How to Add New Intents (New System)

It's very simple:

### Step 1: Add Intent Enum

```python
class Intent(Enum):
    # ... existing intents ...
    LOW_STOCK_PRODUCTS = "low_stock_products"  # New!
```

### Step 2: Add Patterns

```python
self.intent_patterns = {
    # ... existing patterns ...
    Intent.LOW_STOCK_PRODUCTS: [
        r"low stock",
        r"out of stock",
        r"running out",
        r"inventory.*low",
        r"need.*restock"
    ]
}
```

### Step 3: Create Database Tool Function

```python
# In database_tools.py
async def get_low_stock_products(
    shop_id: int,
    threshold: int = 10
) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"shop_id": shop_id, "stock": {"$lt": threshold}}},
        {"$sort": {"stock": 1}},
        {"$limit": 20}
    ]
    result = await mongodb.execute_aggregation("product", pipeline)
    return {
        "products": result,
        "count": len(result),
        "threshold": threshold,
        "shop_id": shop_id
    }
```

### Step 4: Map Intent to Function

```python
# In function_orchestrator.py
self.intent_to_function = {
    # ... existing mappings ...
    Intent.LOW_STOCK_PRODUCTS: self.database_tools.get_low_stock_products
}
```

### Done! ✅

Now queries like:
- "show me low stock products"
- "which items are running out?"
- "inventory that's low"

Will all work correctly!

---

## Parameter Extraction Examples

### Example 1: Time Period

```python
question = "how many orders this week?"

# Pattern match
Intent.ORDER_COUNT → matched!

# Parameter extraction
time_period_pattern = r"(today|yesterday|this week|last week...)"
re.search(time_period_pattern, question)
# Match: "this week"

# Result
intent = Intent.ORDER_COUNT
params = {"time_period": "this week"}

# Function call
await count_orders(shop_id=10, time_period="this week")
```

### Example 2: Limit (Top N)

```python
question = "top 10 products"

# Pattern match
Intent.TOP_PRODUCTS → matched!

# Parameter extraction
limit_pattern = r"top (\d+)"
re.search(limit_pattern, question)
# Match: "10"

# Result
intent = Intent.TOP_PRODUCTS
params = {"limit": 10}

# Function call
await top_products(shop_id=10, limit=10)
```

### Example 3: Multiple Parameters

```python
question = "top 5 customers last month"

# Pattern match
Intent.TOP_CUSTOMERS → matched!

# Parameter extraction
limit_pattern = r"top (\d+)" → "5"
time_period_pattern = r"(last month)" → "last month"

# Result
intent = Intent.TOP_CUSTOMERS
params = {"limit": 5, "time_period": "last month"}

# Function call
await top_customers(shop_id=10, limit=5, time_period="last month")
```

---

## Technical Implementation

### Pattern Matching (Regex)

Both systems use Python's `re` module:

```python
import re

pattern = r"how many categor"
question = "how many categories do i have?"

if re.search(pattern, question):
    print("Match!")  # This will print
```

**Regex patterns used:**

| Pattern | Example Match | Explanation |
|---------|---------------|-------------|
| `r"how many categor"` | "how many **categor**ies" | Literal string match |
| `r"count.*categor"` | "**count my categor**ies" | `.` = any char, `*` = 0+ times |
| `r"top (\d+)"` | "**top 10** products" | `()` = capture group, `\d+` = digits |
| `r"^(hi\|hello)"` | "**hi** there" | `^` = start of string, `\|` = OR |

### Performance

Both classifiers are **extremely fast**:

```python
import time

start = time.time()
intent, params = intent_router.classify(question)
end = time.time()

print(f"Classification time: {(end - start) * 1000:.2f}ms")
# Output: Classification time: 0.15ms
```

**Why so fast?**
- No ML model loading
- No API calls
- Just simple string pattern matching
- Runs in microseconds

---

## Advantages of Rule-Based Classification

### ✅ Pros:

1. **Instant** - No model loading, no API calls
2. **100% Deterministic** - Same input → same output always
3. **No training needed** - Just write patterns
4. **Easy to debug** - Can see exactly which pattern matched
5. **Easy to extend** - Add new patterns anytime
6. **No dependencies** - No ML libraries needed
7. **Works offline** - No internet required
8. **No cost** - No API fees

### ⚠️ Cons:

1. **Manual work** - Need to define patterns for each intent
2. **Limited flexibility** - Can't handle completely novel phrasings
3. **Maintenance** - Need to add patterns as you discover new ways users ask questions

---

## When to Use ML-Based Classification

You would only use ML (like BERT, GPT) for intent classification if:

1. **You have 1000+ intent types** - Too many to manually define patterns
2. **Users ask very creative questions** - Patterns can't capture all variations
3. **Multi-language support** - Easier to train one model than maintain patterns for each language
4. **You have labeled training data** - Thousands of examples to train from

For e-commerce analytics with **10-20 common queries**, **rule-based is perfect**.

---

## Summary

### Old System Issue:
- ❌ Checks "analytical" keywords **before** checking specific KPI patterns
- ❌ The word "how" is too broad and catches count questions
- ❌ "how many categories" → `analytical` → LLM fails → wrong answer

### New System Solution:
- ✅ Checks specific intent patterns **first**
- ✅ More granular patterns per intent
- ✅ "how many categories" → `category_count` → correct function → correct answer

### Both Use:
- ✅ Rule-based regex pattern matching
- ✅ No ML models
- ✅ Fast (< 1ms)
- ✅ Deterministic

### Key Difference:
- **Pattern ordering and specificity** - New system has better pattern design!