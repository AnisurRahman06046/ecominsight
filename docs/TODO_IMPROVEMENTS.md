# EcomInsight - TODO Improvements

## Issues to Fix Tomorrow

---

## ❌ 1. Typos / Spell Check

### Problem:
- "yestarday" (typo) → Returns all-time sales instead of yesterday's sales
- "revenu" → May not match "revenue"
- "produts" → Won't match "products"

### Impact:
- Returns incorrect answers
- User gets confused
- No feedback that there's a typo

### Solution Needed:
**Option A: Fuzzy Matching (Recommended)**
```python
from fuzzywuzzy import fuzz
# Check similarity before routing
# If "yestarday" matches "yesterday" with 90% similarity, use "yesterday"
```

**Option B: Spell Check Library**
```python
from spellchecker import SpellChecker
spell = SpellChecker()
corrected_query = spell.correction(query)
```

### Files to Modify:
- `/app/services/hf_parameter_extractor.py` - Add spell check before date extraction
- `/app/services/llm_mcp_orchestrator.py` - Add spell check at entry point

### Test Cases:
- "yestarday revenue" → Should return yesterday's revenue
- "last mont sales" → Should return last month sales
- "revenu from today" → Should return today's revenue

---

## ❌ 2. Very Complex Multi-Condition Queries

### Problem:
- "Show me orders over $500 from last week that are pending"
- Can handle 2 conditions, struggles with 3+
- Current: date filter + status filter work, but numeric filter may not combine

### Impact:
- Cannot answer complex business questions
- Users need to break down into multiple queries

### Solution Needed:
**Enhanced Parameter Extraction:**
```python
# Current:
filters = {
    "created_at": {"$gte": last_week},
    "status": "Pending"
}

# Need to support:
filters = {
    "created_at": {"$gte": last_week},
    "status": "Pending",
    "grand_total": {"$gt": 500}
}
```

### Files to Modify:
- `/app/services/hf_parameter_extractor.py` - Combine multiple filters
- Test that all filters are applied to MongoDB query

### Test Cases:
- "Orders over $500 from last week that are pending"
- "Customers who spent over $1000 this month"
- "Top products sold yesterday with revenue over $100"

---

## ❌ 3. Comparative Queries

### Problem:
- "Compare this month vs last month"
- "Which month grew the most?"
- Cannot compare two time periods

### Impact:
- No growth analysis
- No month-over-month comparisons
- Critical for business insights

### Solution Needed:
**New Tool: `compare_periods`**
```python
async def compare_periods(
    collection: str,
    shop_id: str,
    metric: str,  # "sales", "orders", "customers"
    period1: Dict,  # e.g., this month
    period2: Dict,  # e.g., last month
    comparison_type: str  # "percentage", "absolute", "both"
) -> Dict:
    # Query both periods
    # Calculate difference
    # Return comparison
```

### Files to Create:
- Add `compare_periods` to `/app/services/mongodb_mcp_service.py`
- Add semantic router examples for comparison queries

### Test Cases:
- "Compare this month vs last month" → "$415,187 vs $2,094,890 (-80.2%)"
- "Which month grew the most?" → "April 2024 (+15% from March)"
- "Year over year growth" → "+25.3%"

---

## ❌ 4. Percentage/Growth Queries

### Problem:
- "What's my growth rate?"
- "Percentage increase this month?"
- No percentage calculations

### Impact:
- Cannot measure growth
- No KPI tracking
- Missing critical business metrics

### Solution Needed:
**New Tool: `calculate_growth`**
```python
async def calculate_growth(
    collection: str,
    shop_id: str,
    metric: str,
    time_period: str,  # "month", "week", "year"
    growth_type: str  # "percentage", "absolute"
) -> Dict:
    # Get current period value
    # Get previous period value
    # Calculate: ((current - previous) / previous) * 100
    # Return growth rate
```

### Files to Modify:
- `/app/services/mongodb_mcp_service.py` - Add calculate_growth tool
- `/app/services/semantic_router.py` - Add growth query examples

### Test Cases:
- "What's my growth rate this month?" → "+15.3%"
- "Percentage increase in orders?" → "Orders grew by 12%"
- "Revenue growth compared to last year?" → "+45.2%"

---

## ❌ 5. Product-Specific Filters

### Problem:
- "Sales of product X"
- "Orders containing Product Y"
- Cannot filter by specific product names

### Impact:
- Cannot analyze individual products
- No product-level insights

### Solution Needed:
**Product Name Extraction:**
```python
def _extract_product_filter(self, query: str) -> Optional[Dict]:
    # Extract product name from query
    # "sales of Designer T-Shirt" → product_name: "Designer T-Shirt"
    # Use regex or NER model
    # Match against product collection
    return {"product_name": {"$regex": product_name, "$options": "i"}}
```

### Files to Modify:
- `/app/services/hf_parameter_extractor.py` - Add product name extraction
- May need to query product collection first to validate names

### Test Cases:
- "Sales of Designer Edition Calligraphy T Shirt" → Show specific product sales
- "How many orders contain Product X?" → Count orders with that product
- "Revenue from T-shirts" → Filter by product name pattern

---

## ❌ 6. Customer-Specific Queries

### Problem:
- "Orders from customer John Doe"
- "What did customer X buy?"
- Cannot filter by customer name

### Impact:
- Cannot analyze individual customers
- No customer-level insights

### Solution Needed:
**Customer Name Extraction:**
```python
def _extract_customer_filter(self, query: str) -> Optional[Dict]:
    # Extract customer name from query
    # "orders from Sajib kumar nag" → customer_name: "Sajib kumar nag"
    # Use NER (Named Entity Recognition) model
    # Or regex patterns for "from customer X", "by X", "customer named X"
    return {"customer_name": {"$regex": customer_name, "$options": "i"}}
```

### Files to Modify:
- `/app/services/hf_parameter_extractor.py` - Add customer name extraction
- May need fuzzy matching since names can have variations

### Test Cases:
- "Orders from Sajib kumar nag" → Show orders from that customer
- "What did customer John buy?" → List products purchased
- "How much did customer X spend?" → Total spending for that customer

---

## ❌ 7. Price Range Queries (Partially Implemented)

### Problem:
- "Products between $50 and $100"
- "Orders over $1000"
- Limited numeric filtering (code exists but may not work well)

### Impact:
- Cannot filter by price ranges
- No revenue segmentation

### Solution Needed:
**Test & Improve Existing Code:**

Already exists in `hf_parameter_extractor.py`:
```python
def _extract_numeric_filter(self, query: str) -> Optional[Dict]:
    # Greater than patterns
    gt_patterns = [r'more than \$?(\d+)', r'over \$?(\d+)', ...]
    # Less than patterns
    lt_patterns = [r'less than \$?(\d+)', r'under \$?(\d+)', ...]
    # Between pattern
    between_match = re.search(r'between \$?(\d+) and \$?(\d+)', query)
```

**Need to:**
1. Test if it works with calculate_sum
2. Add semantic router examples
3. Ensure filters are combined with other filters

### Files to Modify:
- `/app/services/semantic_router.py` - Add price range query examples
- Test existing numeric filter code

### Test Cases:
- "Orders over $1000" → Count/sum orders > $1000
- "Products between $50 and $100" → List products in that range
- "Customers who spent over $5000" → Top spenders above threshold

---

## ❌ 8. Multi-Language Support

### Problem:
- Only English supported
- "¿Cuántos productos tengo?" (Spanish) → Won't work
- "আমার কত অর্ডার আছে?" (Bengali) → Won't work

### Impact:
- Cannot serve non-English users
- Limited market reach

### Solution Needed:
**Option A: Translation Layer (Easier)**
```python
from googletrans import Translator
translator = Translator()

# Translate to English first
if detect_language(query) != "en":
    query = translator.translate(query, dest='en').text
    # Process as normal
    # Translate response back
```

**Option B: Multi-language Models (Better)**
```python
# Use multilingual sentence-transformers
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# This model supports 50+ languages
```

### Files to Modify:
- `/app/services/semantic_router.py` - Use multilingual model
- `/app/api/main.py` - Add language detection

### Test Cases:
- Spanish: "¿Cuántos productos tengo?" → "Hay 971 productos"
- Bengali: "গতকালের বিক্রয়?" → "Total sales: $48,560.00"
- French: "Combien de commandes?" → "Il y a 35,502 commandes"

---

## Priority Order (Recommendation)

### **HIGH PRIORITY** (Do First)
1. ✅ **Typos / Spell Check** - Affects many queries, easy to implement
2. ✅ **Price Range Queries** - Code already exists, just needs testing
3. ✅ **Multi-Condition Queries** - Critical for real-world use

### **MEDIUM PRIORITY** (Do Second)
4. ⚠️ **Comparative Queries** - Important for business insights
5. ⚠️ **Growth/Percentage Queries** - Related to #4, important for KPIs

### **LOW PRIORITY** (Do Later)
6. 🔵 **Product-Specific Filters** - Nice to have, complex to implement
7. 🔵 **Customer-Specific Filters** - Nice to have, complex to implement
8. 🔵 **Multi-Language** - Depends on target market

---

## Estimated Time

| Feature | Complexity | Est. Time |
|---------|-----------|-----------|
| 1. Spell Check | Easy | 2-3 hours |
| 2. Multi-Condition | Medium | 4-6 hours |
| 3. Comparisons | Hard | 8-10 hours |
| 4. Growth Calc | Medium | 4-6 hours |
| 5. Product Filters | Hard | 6-8 hours |
| 6. Customer Filters | Hard | 6-8 hours |
| 7. Price Range (test) | Easy | 1-2 hours |
| 8. Multi-Language | Medium | 6-8 hours |

**Total: 37-51 hours (1-2 weeks of work)**

---

## Quick Wins (Can Do Tomorrow Morning)

### 🚀 Quick Win #1: Spell Check (2 hours)
```bash
pip install pyspellchecker
# Add to hf_parameter_extractor.py
# Test with "yestarday" → should work
```

### 🚀 Quick Win #2: Test Price Range (1 hour)
```python
# Test existing code with:
# "Orders over $1000"
# "Products between $50 and $100"
# If broken, fix regex patterns
```

### 🚀 Quick Win #3: Better Error Messages (1 hour)
```python
# When typo detected:
return {
    "answer": "Did you mean 'yesterday'? No results found for 'yestarday'",
    "suggestion": corrected_query
}
```

---

## Testing Strategy

For each feature, create test file:
```python
# test_feature_X.py
test_queries = [
    {"query": "...", "expected": "..."},
    {"query": "...", "expected": "..."},
]

for test in test_queries:
    result = call_api(test["query"])
    assert test["expected"] in result["answer"]
```

---

## Notes
- Current system handles **90-95%** of typical queries
- These improvements will push it to **98-99%**
- Focus on HIGH PRIORITY items first for maximum impact
- Test thoroughly before deploying each feature

---

**Last Updated:** 2025-10-07
**Status:** Ready for implementation tomorrow
