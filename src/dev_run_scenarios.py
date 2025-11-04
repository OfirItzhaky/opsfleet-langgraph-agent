# dev_run_scenarios.py
from src.graph import build_graph
from dev_scenarios import DEV_SCENARIOS

def run_one(graph, scenario):
    user_query = scenario["query"]
    result = graph.invoke({"input": user_query})
    # depending on how your respond_node saves it:
    print("=" * 80)
    print(scenario["id"], "→", user_query)
    print(result.get("response") or result)
    return result

if __name__ == "__main__":
    graph = build_graph()
    for s in DEV_SCENARIOS:
        run_one(graph, s)
