from src.graph import build_graph
from src.agent_state import AgentState
from src.utils.logging import setup_logging, RequestContext, get_logger

logger = get_logger(__name__)


def run_cli() -> None:
    setup_logging()
    graph = build_graph()

    logger.info("CLI started", extra={"mode": "interactive"})
    print("\n=== Data Agent (thelook_ecommerce) ===")
    print("Type 'exit' to quit at any time.\n")

    # --- friendly intro for first run ---
    print("You can ask business-style questions like:")
    print("  • show me the top revenue products from the last 30 days")
    print("  • which countries bought the most last month?")
    print("  • find high value customers and tell me what they are buying\n")

    first_turn = True

    while True:
        prompt = "ask> " if first_turn else "next question> "
        user_text = input(prompt).strip()
        if user_text.lower() in {"exit", "quit"}:
            logger.info("CLI exiting", extra={"reason": "user_request"})
            print("bye.")
            break

        first_turn = False
        request_id = RequestContext.start_request(user_text)
        logger.info("New query received", extra={
            "request_id": request_id,
            "query": user_text,
            "query_length": len(user_text)
        })

        state = AgentState(user_query=user_text)

        try:
            result = graph.invoke(state)
            output = result.get("response") or "No response was produced by the agent."
            logger.info("Query completed successfully", extra={
                "request_id": request_id,
                "response_length": len(output),
                "template_used": result.get("template_id"),
                "total_llm_cost_usd": round(result.get("total_llm_cost", 0.0), 6),
                "llm_calls_count": result.get("llm_calls_count", 0)
            })
            print("\n" + output + "\n")
        except Exception as exc:
            logger.error("Query failed", extra={
                "request_id": request_id,
                "error": str(exc),
                "error_type": exc.__class__.__name__
            }, exc_info=True)
            print(f"error: {exc}")
        finally:
            RequestContext.clear()



if __name__ == "__main__":
    run_cli()
