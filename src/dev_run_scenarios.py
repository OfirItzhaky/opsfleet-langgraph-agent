# src/dev_run_scenarios.py
import time, json
from src.graph import build_graph
from dev_scenarios import DEV_SCENARIOS
import sys
sys.stdout.reconfigure(line_buffering=True)

def run_scenarios():
    graph = build_graph()
    all_results = []

    for scenario in DEV_SCENARIOS:
        t0 = time.time()
        out = graph.invoke({"user_query": scenario["query"]})
        dt = time.time() - t0

        template_id = out.get("template_id")
        params = out.get("params")
        response_text = out.get("response") or str(out)

        print("=" * 80)
        print(f"{scenario['id']} ({dt:.3f}s) → {scenario['query']}")
        print(response_text)

        all_results.append({
            "id": scenario["id"],
            "query": scenario["query"],
            "elapsed_sec": round(dt, 3),
            "template_id": template_id,
            "params": params,
            "response": response_text,
        })

    print("\n===== ALL SCENARIOS DUMP =====")
    print(json.dumps(all_results, indent=2))

if __name__ == "__main__":
    run_scenarios()
