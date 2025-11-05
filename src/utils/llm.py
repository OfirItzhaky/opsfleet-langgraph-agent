from typing import Any, Dict, Optional
from langchain_core.messages import AIMessage

from src.config import calculate_llm_cost
from src.utils.logging import get_logger

def extract_text(resp: Any) -> str:
    """
    Normalize LLM responses to plain text.
    Works for AIMessage and plain strings.
    """
    if isinstance(resp, AIMessage):
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    return str(resp)


def extract_text(resp: Any) -> str:
    if isinstance(resp, AIMessage):
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    return str(resp)


def log_llm_usage(
    logger: get_logger,
    node_name: str,
    resp: AIMessage,
    model: str,
    duration_ms: float,
    extra_context: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Same signature as your current one — just more robust about
    where it looks for token counts.
    """
    # 1) try modern attr first
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    # A. some langchain versions put it here
    if hasattr(resp, "usage_metadata") and resp.usage_metadata:
        um = resp.usage_metadata
        input_tokens = (
            um.get("input_tokens")
            or um.get("prompt_tokens")
            or um.get("prompt_token_count")
            or 0
        )
        output_tokens = (
            um.get("output_tokens")
            or um.get("completion_tokens")
            or um.get("candidates_token_count")
            or 0
        )
        total_tokens = um.get("total_tokens") or (input_tokens + output_tokens)

    # B. your current path: response_metadata → usage_metadata
    elif getattr(resp, "response_metadata", None):
        rm = resp.response_metadata
        um = rm.get("usage_metadata", {})
        input_tokens = (
            um.get("prompt_token_count")
            or um.get("input_tokens")
            or um.get("prompt_tokens")
            or 0
        )
        output_tokens = (
            um.get("candidates_token_count")
            or um.get("output_tokens")
            or um.get("completion_tokens")
            or 0
        )
        total_tokens = um.get("total_token_count") or (input_tokens + output_tokens)

    # 2) compute cost
    cost = calculate_llm_cost(model, input_tokens, output_tokens)

    # 3) log
    data = {
        "node": node_name,
        "model": model,
        "llm_duration_ms": round(duration_ms, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(cost, 6),
    }
    if extra_context:
        data.update(extra_context)

    # use your logging pipeline
    logger.info(f"{node_name} LLM call completed", extra=data)

    # if still zero, tell yourself in the logs why
    if total_tokens == 0:
        logger.warning(
            f"{node_name} LLM response had no detectable token usage",
            extra={
                "node": node_name,
                "response_metadata": getattr(resp, "response_metadata", {}),
                "has_usage_metadata": bool(getattr(resp, "usage_metadata", None)),
            },
        )

    return cost


def strip_code_fences(text: str) -> str:
    """
    Remove ```...``` fences (often used when LLM returns JSON).
    """
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    # drop first fence
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    # drop last fence
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)
