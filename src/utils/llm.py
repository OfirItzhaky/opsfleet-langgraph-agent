from typing import Any
from langchain_core.messages import AIMessage

def extract_text(resp: Any) -> str:
    """
    Normalize LLM responses to plain text.
    Works for AIMessage and plain strings.
    """
    if isinstance(resp, AIMessage):
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    return str(resp)


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
