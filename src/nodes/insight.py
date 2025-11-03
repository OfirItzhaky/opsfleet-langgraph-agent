from typing import Any, Dict, List
import os
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

INSIGHTS_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "insights.md"


def _build_insight_prompt(results: Dict[str, Any]) -> str:
    """Serialize numeric results + append instruction template."""
    summary = results.get("summary") or {}
    top_products = results.get("top_products") or []
    by_geo = results.get("by_geo") or []
    notes = results.get("notes") or []

    lines: List[str] = []
    lines.append("Validated e-commerce results below. Do NOT invent numbers.")
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

    data_block = "\n".join(lines)

    # load markdown instructions if file exists
    if PROMPT_FILE.exists():
        prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
        return data_block + "\n\n" + prompt_template

    # fallback to inline instructions
    return data_block + (
        "\n\nInsights:\n- ...\n\nActions:\n- ...\n\nFollow-ups:\n- ...\n"
        "Use only the data above. Do not invent numbers."
    )


def insight_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Turn numeric aggregates from results_node into narrative insights."""
    results = state.get("results") or {}

    prompt = _build_insight_prompt(results)

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        # fail soft
        state["insights"] = {
            "bullets": ["(insight service unavailable: missing GOOGLE_API_KEY)"],
            "actions": [],
            "followups": [],
        }
        return state

    try:
        llm = ChatGoogleGenerativeAI(
            model=INSIGHTS_MODEL,
            google_api_key=api_key,
        )
        resp = llm.invoke(prompt)
        # langchain chat models return an AIMessage
        if isinstance(resp, AIMessage):
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
        else:
            text = str(resp)
    except Exception as exc:
        state["insights"] = {
            "bullets": [f"(insight service error: {exc})"],
            "actions": [],
            "followups": [],
        }
        return state

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

    # normalize counts
    bullets = bullets[:7]
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
