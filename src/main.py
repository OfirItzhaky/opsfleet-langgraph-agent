from src.graph import build_graph
from src.state import AgentState
from src.utils.logging import setup_logging


def run_cli() -> None:
    setup_logging()
    graph = build_graph()
    print("Opsfleet Data Agent (thelook_ecommerce). Type 'exit' to quit.\n")

    while True:
        user_text = input("ask> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            print("bye.")
            break

        state = AgentState(user_query=user_text)

        try:

            result = graph.invoke(state.model_dump())

            output = (
                result.get("response_text")
                or result.get("response")
                or "No response was produced by the agent."
            )
            print("\n" + output + "\n")
        except Exception as exc:
            import logging
            logging.exception("error while running agent")
            print(f"error: {exc}")


if __name__ == "__main__":
    run_cli()
