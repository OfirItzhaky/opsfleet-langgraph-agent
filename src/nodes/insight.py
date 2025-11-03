
from typing import Any, Dict, List

import os
from google import genai  # google-genai >= 1.0.0 style
# If your proj used old google.generativeai, adapt the import & client init.

INSIGHTS_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def _build_insight_prompt(results: Dict[str, Any]) -> str:
    """
    Turn the Python aggregates from results_node() into a stable text
    that we can feed into Gemini along with strict instructions.
    """
    # We only serialize what we have; if some keys are missing, we say so.
    summary = results.get("summary") or {}
    top_products = results.get("top_products") or []
    by_geo = results.get("by_geo") or []
    notes = results.get("notes") or []

    lines = []
    lines.append("You are an e-commerce analytics assistant.")
    lines.append("Below are computed, validated results from BigQuery. "
                 "You must NOT create or guess new metrics.")
    lines.append("")
    lines.append("== SUMMARY ==")
    if summary:
        for k, v in summary.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (no summary available)")

    lines.append("")
    lines.append("== TOP PRODUCTS ==")
    if top_products:
        for p in top_products[:10]:
            # keep it short to control tokens
            name = p.get("name") or p.get("product_id") or "unknown"
            revenue = p.get("revenue", "n/a")
            lines.append(f"- {name}: revenue={revenue}")
    else:
        lines.append("- (no top products available)")

    lines.append("")
    lines.append("== BY GEO ==")
    if by_geo:
        for g in by_geo[:10]:
            geo = g.get("country") or g.get("state") or "area"
            val = g.get("revenue") or g.get("orders") or "n/a"
            lines.append(f"- {geo}: {val}")
    else:
        lines.append("- (no geo breakdown available)")

    if notes:
        lines.append("")
        lines.append("== NOTES ==")
        for n in notes:
            lines.append(f"- {n}")

    # Now the actual instruction part comes from the prompt file (see below),
    # but we can append it here if we want a single-string prompt.
    lines.append("")
    lines.append("Generate 4-7 insight bullets, 1-3 recommended actions, "
                 "and 2 follow-up questions.")
    lines.append("Reference only the data above. If a metric is missing, say so.")

    return "\n".join(lines)


def insight_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Turn numeric aggregates from results_node into narrative insights.
    Expected to be called in the LangGraph step 12.
    """
    results = state.get("results") or {}

    # Build prompt
    prompt = _build_insight_prompt(results)

    # Prepare client
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # fail soft: return empty insights but keep graph going
        state["insights"] = {
            "bullets": ["(insight service unavailable: missing GOOGLE_API_KEY)"],
            "actions": [],
            "followups": []
        }
        return state

    client = genai.Client(api_key=api_key)

    # Call model
    try:
        resp = client.models.generate_content(
            model=INSIGHTS_MODEL,
            contents=prompt,
        )
        # We expect a friendly, structured-ish text. We'll do a very simple parser.
        text = resp.text or ""
    except Exception as exc:
        # fail soft
        state["insights"] = {
            "bullets": [f"(insight service error: {exc})"],
            "actions": [],
            "followups": []
        }
        return state

    # --- Simple parsing strategy ---
    # We will look for our 3 sections by markers. If the model followed the prompt,
    # it will output e.g.:
    # Insights:
    # - ...
    # Actions:
    # - ...
    # Follow-ups:
    # - ...
    bullets: List[str] = []
    actions: List[str] = []
    followups: List[str] = []

    current = None
    for line in text.splitlines():
        line = line.strip()
        lower = line.lower()
        if "insight" in lower:
            current = "insights"
            continue
        if "action" in lower:
            current = "actions"
            continue
        if "follow" in lower:
            current = "followups"
            continue
        if line.startswith("-") or line.startswith("*"):
            item = line.lstrip("-* ").strip()
            if not item:
                continue
            if current == "insights":
                bullets.append(item)
            elif current == "actions":
                actions.append(item)
            elif current == "followups":
                followups.append(item)

    # Enforce counts
    bullets = bullets[:7]  # 4–7 wanted
    if len(bullets) < 4:
        # pad so downstream doesn't break
        while len(bullets) < 4:
            bullets.append("(no further insight provided)")
    actions = actions[:3]
    followups = followups[:2]

    state["insights"] = {
        "bullets": bullets,
        "actions": actions,
        "followups": followups,
    }
    return state
