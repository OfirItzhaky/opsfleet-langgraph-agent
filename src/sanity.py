"""
Sanity checks to verify environment configuration, Gemini key, and BigQuery access.
"""

from src.utils.logging import setup_logging
from src.config import require_env, GEMINI_API_KEY, GCP_PROJECT_ID
from src.clients.bq_client import BigQueryRunner


def main():
    setup_logging()
    print("== Sanity checks ==")

    # 1️⃣ Verify environment
    try:
        require_env()
        print(f"GEMINI_API_KEY present (length={len(GEMINI_API_KEY)})")
        print(f"GCP_PROJECT_ID={GCP_PROJECT_ID or '(not set: using ADC default)'}")
    except Exception as e:
        print("Env error:", e)
        return

    # 2️⃣ Verify BigQuery connectivity
    try:
        bq = BigQueryRunner(project_id=GCP_PROJECT_ID)
        df = bq.execute_query("SELECT 1 AS ok;")
        print("BigQuery ok:", df.to_dict("records"))
    except Exception as e:
        print("BigQuery error:", e)
        return

    print("All basic checks passed.")


if __name__ == "__main__":
    main()
