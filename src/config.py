import os
from dotenv import load_dotenv

# Load variables from a local .env file (ignored by git)
load_dotenv()

# Public config values your code will import
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY", "")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID") or None
GEMINI_MODEL = "gemini-2.5-flash"
def require_env() -> None:
    """
    Raise a clear error if required env vars are missing.
    Keep this minimal—right now only Gemini key is strictly required.
    """
    missing = []
    if not GOOGLE_API_KEY:
        missing.append("GOOGLE_API_KEY")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
