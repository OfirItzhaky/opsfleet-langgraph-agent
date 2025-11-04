# Plan Refinement Prompt (LLM)

You are helping refine an analytics plan for a fixed **e-commerce dataset**.  
You will receive:

1. The user's **original question**  
2. The **intent-derived template id** chosen by a deterministic rule  
3. The current **template parameters**

---

## Your task
ONLY adjust the parameters so they better match the user's natural-language question.  

When refining:
- Detect and include **geographic filters** mentioned in the question  
  (e.g., "US", "Canada", "Germany") as a list under key `"countries"`.
- Detect and include **department or demographic filters**  
  (e.g., "men’s", "women’s", "kids") as `"department"`.
- Detect and normalize **time ranges**:
  - "this quarter" → last 90 days
  - "last year" → last 365 days
  - "last month" → last 30 days
  Always set `"end_date": "CURRENT_DATE()"`.
- If both geographic and product/brand cues appear, keep
  `template_id = "q_top_products"` but include the extracted filters.
- Do **not** add unrelated keys; stay concise and valid JSON.
- Do **not** just copy the example below; tailor the params to the actual user question.

Return **STRICT JSON** with exactly these keys:

```json
{
  "template_id": "q_geo_sales",
  "params": {
    "level": "country",
    "limit": 200,
    "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)",
    "end_date": "CURRENT_DATE()"
  }
}
```