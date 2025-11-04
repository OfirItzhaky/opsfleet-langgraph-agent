# src/dev_run_scenarios.py
import time, json
from src.graph import build_graph
from src.dev_scenarios import DEV_SCENARIOS
from src.utils.logging import setup_logging, get_logger, RequestContext
import sys
sys.stdout.reconfigure(line_buffering=True)

# Setup logging
setup_logging()
logger = get_logger(__name__)

def run_scenarios():
    graph = build_graph()
    all_results = []
    
    logger.info("Starting scenario batch", extra={
        "total_scenarios": len(DEV_SCENARIOS)
    })

    for idx, scenario in enumerate(DEV_SCENARIOS, 1):
        # Start request context for tracing
        request_id = RequestContext.start_request(scenario["query"])
        
        logger.info("Scenario starting", extra={
            "scenario_id": scenario["id"],
            "scenario_num": f"{idx}/{len(DEV_SCENARIOS)}",
            "query": scenario["query"],
            "request_id": request_id
        })
        
        t0 = time.time()
        try:
            out = graph.invoke({"user_query": scenario["query"]})
            dt = time.time() - t0

            template_id = out.get("template_id")
            params = out.get("params")
            response_text = out.get("response") or str(out)
            
            logger.info("Scenario completed", extra={
                "scenario_id": scenario["id"],
                "scenario_num": f"{idx}/{len(DEV_SCENARIOS)}",
                "elapsed_sec": round(dt, 3),
                "template_id": template_id,
                "intent": out.get("intent"),
                "response_length": len(response_text),
                "request_id": request_id
            })

            # Still print for quick visual feedback
            print("=" * 80)
            print(f"[{idx}/{len(DEV_SCENARIOS)}] {scenario['id']} ({dt:.3f}s) → {scenario['query']}")
            print(f"Intent: {out.get('intent')} | Template: {template_id}")
            print("-" * 80)
            print(response_text[:300] + "..." if len(response_text) > 300 else response_text)

            all_results.append({
                "id": scenario["id"],
                "query": scenario["query"],
                "elapsed_sec": round(dt, 3),
                "template_id": template_id,
                "intent": out.get("intent"),
                "params": params,
                "response": response_text,
                "request_id": request_id
            })
            
        except Exception as e:
            dt = time.time() - t0
            logger.error("Scenario failed", extra={
                "scenario_id": scenario["id"],
                "scenario_num": f"{idx}/{len(DEV_SCENARIOS)}",
                "elapsed_sec": round(dt, 3),
                "error": str(e),
                "request_id": request_id
            }, exc_info=True)
            
            print("=" * 80)
            print(f"[{idx}/{len(DEV_SCENARIOS)}] {scenario['id']} FAILED ({dt:.3f}s)")
            print(f"Error: {str(e)}")
            
            all_results.append({
                "id": scenario["id"],
                "query": scenario["query"],
                "elapsed_sec": round(dt, 3),
                "error": str(e),
                "request_id": request_id
            })
        
        finally:
            RequestContext.clear()
    
    # Summary logging
    total_time = sum(r.get("elapsed_sec", 0) for r in all_results)
    successful = len([r for r in all_results if "error" not in r])
    failed = len([r for r in all_results if "error" in r])
    
    logger.info("Scenario batch completed", extra={
        "total_scenarios": len(DEV_SCENARIOS),
        "successful": successful,
        "failed": failed,
        "total_time_sec": round(total_time, 3),
        "avg_time_sec": round(total_time / len(DEV_SCENARIOS), 3) if DEV_SCENARIOS else 0
    })

    print("\n" + "=" * 80)
    print("===== ALL SCENARIOS SUMMARY =====")
    print("=" * 80)
    print(f"Total: {len(DEV_SCENARIOS)} | Successful: {successful} | Failed: {failed}")
    print(f"Total time: {total_time:.3f}s | Average: {total_time/len(DEV_SCENARIOS):.3f}s")
    print("\n===== DETAILED RESULTS (JSON) =====")
    print(json.dumps(all_results, indent=2))

if __name__ == "__main__":
    run_scenarios()
