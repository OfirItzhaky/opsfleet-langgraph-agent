# src/semantic_intent.py

from typing import Dict, Any, List
from sentence_transformers import SentenceTransformer, util

# predefine your shapes
SHAPES = [
    {
        "id": "geo_sales_top",
        "text": "top countries by revenue, which countries bought the most, sales by country",
        "template_id": "q_geo_sales",
        "params": {"sort_dir": "DESC", "level": "country"},
    },
    {
        "id": "geo_sales_bottom",
        "text": "countries that bought the least, lowest revenue geos, worst performing countries",
        "template_id": "q_geo_sales",
        "params": {"sort_dir": "ASC", "level": "country"},
    },
    {
        "id": "product_performance",
        "text": "top products by revenue, best selling products, product performance",
        "template_id": "q_top_products",
        "params": {"sort_dir": "DESC"},
    },
    {
        "id": "sales_trend",
        "text": "sales trend over time, monthly sales, seasonality",
        "template_id": "q_sales_trend",
        "params": {},
    },
    # ... segment, etc.
]

_model = SentenceTransformer("all-MiniLM-L6-v2")
_shape_embeddings = _model.encode([s["text"] for s in SHAPES], convert_to_tensor=True)

def resolve_query_shape(user_query: str) -> Dict[str, Any]:
    query_emb = _model.encode(user_query, convert_to_tensor=True)
    scores = util.cos_sim(query_emb, _shape_embeddings)[0]
    best_idx = int(scores.argmax())
    best_shape = SHAPES[best_idx]
    # return only the stuff the plan node needs
    return {
        "template_id": best_shape["template_id"],
        "params": dict(best_shape["params"]),
        "shape_id": best_shape["id"],
        "score": float(scores[best_idx]),
    }
