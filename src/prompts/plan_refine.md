# Plan Refinement Prompt (LLM)

You are helping refine an analytics plan for a fixed **e-commerce dataset**.  
You will receive:

1. The user's **original question**  
2. The **intent-derived template id** chosen by a deterministic rule  
3. The current **template parameters**

---

## Your task
ONLY adjust the parameters so they better match the user's natural-language question.  
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
