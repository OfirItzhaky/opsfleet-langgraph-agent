from src.graph import build_graph
from src.agent_state import AgentState
from src.utils.logging import setup_logging, RequestContext, get_logger

logger = get_logger(__name__)


def run_cli() -> None:
    setup_logging()
    graph = build_graph()
    
    logger.info("CLI started", extra={"mode": "interactive"})
    print("Opsfleet Data Agent (thelook_ecommerce). Type 'exit' to quit.\n")

    while True:
        user_text = input("ask> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            logger.info("CLI exiting", extra={"reason": "user_request"})
            print("bye.")
            break

        # Start request context for tracing
        request_id = RequestContext.start_request(user_text)
        logger.info("New query received", extra={
            "request_id": request_id,
            "query": user_text,
            "query_length": len(user_text)
        })

        state = AgentState(user_query=user_text)

        try:
            result = graph.invoke(state)

            output = (
                    result.get("response")  # main field now
                    or "No response was produced by the agent."
            )
            
            logger.info("Query completed successfully", extra={
                "request_id": request_id,
                "response_length": len(output),
                "template_used": result.get("template_id")
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
            # Clear request context
            RequestContext.clear()


if __name__ == "__main__":
    run_cli()
