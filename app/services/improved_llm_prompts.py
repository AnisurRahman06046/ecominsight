"""
Improved LLM Prompts with Few-Shot Learning
Provides better examples and instructions for MongoDB query generation
"""

def get_mongodb_generation_prompt(schema_context: str, question: str, shop_id: int) -> str:
    """
    Generate an improved prompt with few-shot learning examples
    """

    prompt = f"""You are a MongoDB query expert. Generate ONLY valid MongoDB aggregation pipelines.

DATABASE SCHEMA:
{schema_context}

IMPORTANT MONGODB OPERATORS:
- Comparison: $gt, $gte, $lt, $lte, $eq, $ne, $in
- Logical: $and, $or, $not
- Date: $dateFromString, $dateToString, $dayOfMonth, $month, $year
- Aggregation: $sum, $avg, $min, $max, $count
- Array: $unwind, $size, $filter

CRITICAL RULES:
1. ALWAYS start with {{"$match": {{"shop_id": {shop_id}}}}}
2. Use proper MongoDB syntax - no invalid operators
3. For date comparisons, use ISODate format or string comparisons
4. Return ONLY the JSON - no explanations

EXAMPLES OF CORRECT QUERIES:

Example 1 - Count all items in a collection:
User: "How many categories do I have?"
{{
  "collection": "category",
  "pipeline": [
    {{"$match": {{"shop_id": {shop_id}}}}},
    {{"$count": "total"}}
  ],
  "answer_template": "You have {{total}} categories"
}}

Example 2 - Filter with conditions:
User: "Show orders greater than 1000"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": {shop_id}, "grand_total": {{"$gt": 1000}}}}}}
  ],
  "answer_template": "Found {{count}} orders over $1000"
}}

Example 3 - Top N with aggregation:
User: "Top 5 customers by spending"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": {shop_id}}}}},
    {{"$group": {{
      "_id": "$user_id",
      "total_spent": {{"$sum": "$grand_total"}},
      "order_count": {{"$sum": 1}}
    }}}},
    {{"$sort": {{"total_spent": -1}}}},
    {{"$limit": 5}},
    {{"$lookup": {{
      "from": "customer",
      "localField": "_id",
      "foreignField": "id",
      "as": "customer_info"
    }}}}
  ],
  "answer_template": "Top 5 customers by spending"
}}

Example 4 - Group and count by field:
User: "How many orders in each status?"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": {shop_id}}}}},
    {{"$group": {{
      "_id": "$status",
      "count": {{"$sum": 1}}
    }}}},
    {{"$sort": {{"count": -1}}}}
  ],
  "answer_template": "Orders grouped by status"
}}

Example 5 - Date range query:
User: "Orders from last 7 days"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{
      "shop_id": {shop_id},
      "created_at": {{
        "$gte": {{"$dateSubtract": {{
          "startDate": "$$NOW",
          "unit": "day",
          "amount": 7
        }}}}
      }}
    }}}},
    {{"$sort": {{"created_at": -1}}}}
  ],
  "answer_template": "Orders from last 7 days"
}}

Example 6 - Calculate average:
User: "What's my average order value?"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{"shop_id": {shop_id}}}}},
    {{"$group": {{
      "_id": null,
      "avg_value": {{"$avg": "$grand_total"}},
      "total_orders": {{"$sum": 1}}
    }}}}
  ],
  "answer_template": "Average order value: ${{avg_value}}"
}}

Example 7 - Multiple conditions:
User: "Find pending orders over 500"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{
      "shop_id": {shop_id},
      "status": "pending",
      "grand_total": {{"$gt": 500}}
    }}}}
  ],
  "answer_template": "Found {{count}} pending orders over $500"
}}

Example 8 - Revenue calculation:
User: "Total revenue this month"
{{
  "collection": "order",
  "pipeline": [
    {{"$match": {{
      "shop_id": {shop_id},
      "created_at": {{
        "$gte": {{"$dateFromParts": {{"year": {{"$year": "$$NOW"}}, "month": {{"$month": "$$NOW"}}, "day": 1}}}}
      }}
    }}}},
    {{"$group": {{
      "_id": null,
      "total_revenue": {{"$sum": "$grand_total"}},
      "order_count": {{"$sum": 1}}
    }}}}
  ],
  "answer_template": "Total revenue this month: ${{total_revenue}}"
}}

NOW GENERATE A QUERY FOR THIS:
User Question: "{question}"
Shop ID: {shop_id}

Remember:
- Identify the correct collection based on the question
- Use appropriate MongoDB operators
- Include proper aggregation stages when needed
- Return ONLY the JSON with collection, pipeline, and answer_template"""

    return prompt


def get_intent_classification_prompt(schema_context: str, question: str, shop_id: int) -> str:
    """
    Improved intent classification prompt
    """

    prompt = f"""Analyze this query and determine exactly what the user wants from the database.

DATABASE SCHEMA:
{schema_context}

User Question: "{question}"
Shop ID: {shop_id}

Classify the intent and extract parameters. Consider:
1. Which collection(s) are involved
2. What operation is needed (count, filter, aggregate, etc.)
3. Any specific conditions or filters
4. Time ranges if mentioned
5. Sorting or limiting requirements

EXAMPLES:

Q: "How many products do I have?"
{{
  "primary_collection": "product",
  "operation_type": "count",
  "intent": "count all products",
  "filters": {{}},
  "time_range": null,
  "sort_field": null,
  "group_by": null,
  "limit": null,
  "conditions": []
}}

Q: "Show me orders over $1000 from last week"
{{
  "primary_collection": "order",
  "operation_type": "filter",
  "intent": "find high-value recent orders",
  "filters": {{"grand_total": {{"$gt": 1000}}}},
  "time_range": "last_week",
  "sort_field": "created_at",
  "group_by": null,
  "limit": null,
  "conditions": ["grand_total > 1000", "date in last 7 days"]
}}

Q: "Which customers spent the most?"
{{
  "primary_collection": "order",
  "operation_type": "aggregate",
  "intent": "find top customers by spending",
  "filters": {{}},
  "time_range": null,
  "sort_field": "total_spent",
  "group_by": "user_id",
  "limit": 10,
  "conditions": [],
  "needs_calculation": true,
  "calculation_type": "sum"
}}

Q: "Average order value by month"
{{
  "primary_collection": "order",
  "operation_type": "aggregate",
  "intent": "calculate monthly average order values",
  "filters": {{}},
  "time_range": null,
  "sort_field": "month",
  "group_by": "month",
  "limit": null,
  "conditions": [],
  "needs_calculation": true,
  "calculation_type": "average"
}}

Now classify this question:
"{question}"

Return ONLY the JSON classification."""

    return prompt


def get_simple_mongodb_prompt() -> str:
    """
    Get a simplified prompt for basic MongoDB generation
    """

    return """You are a MongoDB expert. Generate queries following these patterns:

PATTERN 1 - COUNT:
{{"$match": {{"shop_id": 10}}}}, {{"$count": "total"}}

PATTERN 2 - FILTER:
{{"$match": {{"shop_id": 10, "field": {{"$operator": value}}}}}}

PATTERN 3 - GROUP:
{{"$match": {{"shop_id": 10}}}},
{{"$group": {{"_id": "$field", "count": {{"$sum": 1}}}}}}

PATTERN 4 - AGGREGATE:
{{"$match": {{"shop_id": 10}}}},
{{"$group": {{"_id": "$field", "total": {{"$sum": "$amount"}}}}},
{{"$sort": {{"total": -1}}}},
{{"$limit": 5}}

PATTERN 5 - DATE RANGE:
{{"$match": {{
  "shop_id": 10,
  "created_at": {{"$gte": "2024-01-01", "$lte": "2024-12-31"}}
}}}}

Generate appropriate pipeline based on the question."""