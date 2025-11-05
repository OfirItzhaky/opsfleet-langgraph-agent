import os
from dotenv import load_dotenv

# Load variables from a local .env file (ignored by git)
load_dotenv()

# Public config values your code will import
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID") or None
GEMINI_MODEL = "gemini-2.5-flash"
# Can use gemini-2.5-pro assuming API KEY with usage allowance

# Setting for either determinsitic node or dynamic using llm
INTENT_MODE  = "Deterministic"

# Dynamic  - choose to use llm in the intent


# Gemini pricing per 1M tokens
# Source: https://ai.google.dev/pricing
MODEL_PRICING = {
    "gemini-2.5-flash": {
        "input": 0.075,   # $0.075 per 1M input tokens
        "output": 0.30,   # $0.30 per 1M output tokens
    },
    "gemini-2.5-pro": {
        "input": 1.25,    # $1.25 per 1M input tokens
        "output": 5.00,   # $5.00 per 1M output tokens
    },
}

def calculate_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    Calculate the cost of an LLM API call.
    
    Args:
        model: Model name (e.g., "gemini-2.5-flash")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Cost in USD
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        # Fallback to gemini-2.5-flash pricing if model unknown
        pricing = MODEL_PRICING["gemini-2.5-flash"]
    
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    
    return input_cost + output_cost

def require_env() -> None:
    """
    Raise a clear error if required env vars are missing.
    Keep this minimal—right now only Gemini key is strictly required.
    """
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GOOGLE_API_KEY")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
