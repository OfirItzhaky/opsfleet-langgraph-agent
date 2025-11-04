# src/dev_run_scenarios_timed.py
"""
Enhanced scenario runner with detailed node-level timing to identify bottlenecks.
"""
import time
import json
import sys
from typing import Dict, Any, List
from langgraph.graph import StateGraph

sys.stdout.reconfigure(line_buffering=True)

from src.graph import build_graph
from src.dev_scenarios import DEV_SCENARIOS
from src.agent_state import AgentState


class TimingWrapper:
    """Wraps a node function to measure execution time."""
    
    def __init__(self, node_name: str, original_func):
        self.node_name = node_name
        self.original_func = original_func
        self.timings: List[float] = []
    
    def __call__(self, state: AgentState, *args, **kwargs) -> AgentState:
        t0 = time.time()
        result = self.original_func(state, *args, **kwargs)
        elapsed = time.time() - t0
        self.timings.append(elapsed)
        return result
    
    def get_stats(self):
        if not self.timings:
            return {"count": 0, "total": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(self.timings),
            "total": round(sum(self.timings), 3),
            "avg": round(sum(self.timings) / len(self.timings), 3),
            "min": round(min(self.timings), 3),
            "max": round(max(self.timings), 3),
        }


def build_instrumented_graph():
    """Build graph with timing wrappers around each node."""
    from src.nodes.intent import intent_node
    from src.nodes.plan import plan_node
    from src.nodes.sqlgen import sqlgen_node
    from src.nodes.exec import exec_node
    from src.nodes.results import results_node
    from src.nodes.insight import insight_node
    from src.nodes.respond import respond_node
    
    # Create timing wrappers
    timing_wrappers = {
        "intent": TimingWrapper("intent", intent_node),
        "plan": TimingWrapper("plan", plan_node),
        "sqlgen": TimingWrapper("sqlgen", sqlgen_node),
        "exec": TimingWrapper("exec", exec_node),
        "results": TimingWrapper("results", results_node),
        "insight": TimingWrapper("insight", insight_node),
        "respond": TimingWrapper("respond", respond_node),
    }
    
    # Build graph with wrapped nodes
    sg = StateGraph(AgentState)
    
    for node_name, wrapper in timing_wrappers.items():
        sg.add_node(node_name, wrapper)
    
    sg.set_entry_point("intent")
    sg.add_edge("intent", "plan")
    sg.add_edge("plan", "sqlgen")
    sg.add_edge("sqlgen", "exec")
    sg.add_edge("exec", "results")
    sg.add_edge("results", "insight")
    sg.add_edge("insight", "respond")
    from langgraph.graph import END
    sg.add_edge("respond", END)
    
    return sg.compile(), timing_wrappers


def format_timing_table(timings: Dict[str, Dict[str, float]], total_time: float) -> str:
    """Format node timings as a pretty table."""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("NODE TIMING BREAKDOWN")
    lines.append("=" * 80)
    lines.append(f"{'Node':<12} {'Time (s)':<10} {'% of Total':<12} {'Calls':<8}")
    lines.append("-" * 80)
    
    # Sort by total time descending
    sorted_nodes = sorted(timings.items(), key=lambda x: x[1]['total'], reverse=True)
    
    for node_name, stats in sorted_nodes:
        if stats['count'] > 0:
            pct = (stats['total'] / total_time * 100) if total_time > 0 else 0
            lines.append(
                f"{node_name:<12} {stats['total']:<10.3f} {pct:<12.1f} {stats['count']:<8}"
            )
    
    lines.append("-" * 80)
    lines.append(f"{'TOTAL':<12} {total_time:<10.3f} {'100.0':<12} {'':<8}")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def run_scenarios():
    """Run all scenarios with detailed timing instrumentation."""
    print("\n🚀 Starting instrumented scenario run...")
    print(f"Running {len(DEV_SCENARIOS)} scenarios\n")
    
    graph, timing_wrappers = build_instrumented_graph()
    all_results = []
    overall_start = time.time()
    
    for idx, scenario in enumerate(DEV_SCENARIOS, 1):
        print(f"\n{'=' * 80}")
        print(f"[{idx}/{len(DEV_SCENARIOS)}] Running: {scenario['id']}")
        print(f"Query: {scenario['query']}")
        print(f"{'=' * 80}")
        
        scenario_start = time.time()
        
        try:
            out = graph.invoke({"user_query": scenario["query"]})
            scenario_elapsed = time.time() - scenario_start
            
            template_id = out.get("template_id")
            params = out.get("params")
            response_text = out.get("response") or str(out)
            intent = out.get("intent")
            
            # Collect per-node timings for this scenario
            node_timings = {}
            for node_name, wrapper in timing_wrappers.items():
                if wrapper.timings:
                    node_timings[node_name] = wrapper.timings[-1]  # Get last timing
            
            print(f"\n✓ Completed in {scenario_elapsed:.3f}s")
            print(f"\n📊 Node Breakdown:")
            for node_name in ["intent", "plan", "sqlgen", "exec", "results", "insight", "respond"]:
                if node_name in node_timings:
                    t = node_timings[node_name]
                    pct = (t / scenario_elapsed * 100) if scenario_elapsed > 0 else 0
                    bar = "█" * int(pct / 2)  # Visual bar
                    print(f"  {node_name:<10} {t:>6.3f}s ({pct:>5.1f}%) {bar}")
            
            print(f"\n💡 Response Preview:")
            preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
            print(f"  {preview}")
            
            all_results.append({
                "id": scenario["id"],
                "query": scenario["query"],
                "elapsed_sec": round(scenario_elapsed, 3),
                "intent": intent,
                "template_id": template_id,
                "params": params,
                "node_timings": {k: round(v, 3) for k, v in node_timings.items()},
                "response_preview": response_text[:300],
                "expected": scenario.get("expect"),
            })
            
        except Exception as e:
            scenario_elapsed = time.time() - scenario_start
            print(f"\n❌ Error in {scenario_elapsed:.3f}s: {str(e)}")
            all_results.append({
                "id": scenario["id"],
                "query": scenario["query"],
                "elapsed_sec": round(scenario_elapsed, 3),
                "error": str(e),
                "expected": scenario.get("expect"),
            })
    
    overall_elapsed = time.time() - overall_start
    
    # Print aggregate timing statistics
    print("\n\n" + "=" * 80)
    print("📈 AGGREGATE TIMING STATISTICS")
    print("=" * 80)
    
    total_scenario_time = sum(r['elapsed_sec'] for r in all_results if 'elapsed_sec' in r)
    
    for node_name, wrapper in timing_wrappers.items():
        stats = wrapper.get_stats()
        if stats['count'] > 0:
            print(f"\n{node_name.upper()}:")
            print(f"  Total:   {stats['total']:.3f}s ({stats['total']/total_scenario_time*100:.1f}% of all scenarios)")
            print(f"  Average: {stats['avg']:.3f}s")
            print(f"  Min:     {stats['min']:.3f}s")
            print(f"  Max:     {stats['max']:.3f}s")
            print(f"  Calls:   {stats['count']}")
    
    print(f"\n{'=' * 80}")
    print(f"Total runtime: {overall_elapsed:.3f}s")
    print(f"Scenario time: {total_scenario_time:.3f}s")
    print(f"Overhead:      {overall_elapsed - total_scenario_time:.3f}s")
    print(f"{'=' * 80}")
    
    # Identify bottlenecks
    print("\n\n🔍 BOTTLENECK ANALYSIS")
    print("=" * 80)
    
    node_totals = []
    for node_name, wrapper in timing_wrappers.items():
        stats = wrapper.get_stats()
        if stats['total'] > 0:
            node_totals.append((node_name, stats['total'], stats['avg']))
    
    node_totals.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop bottlenecks by total time:")
    for rank, (node_name, total, avg) in enumerate(node_totals[:3], 1):
        pct = (total / total_scenario_time * 100) if total_scenario_time > 0 else 0
        print(f"  {rank}. {node_name:<10} {total:>7.3f}s ({pct:>5.1f}%) - avg {avg:.3f}s per call")
    
    print("\n" + "=" * 80)
    
    # Save detailed results
    output_file = "scenario_results_timed.json"
    with open(output_file, "w") as f:
        json.dump({
            "summary": {
                "total_scenarios": len(DEV_SCENARIOS),
                "successful": len([r for r in all_results if 'error' not in r]),
                "failed": len([r for r in all_results if 'error' in r]),
                "total_runtime_sec": round(overall_elapsed, 3),
                "total_scenario_time_sec": round(total_scenario_time, 3),
            },
            "node_statistics": {
                node_name: wrapper.get_stats() 
                for node_name, wrapper in timing_wrappers.items()
            },
            "bottlenecks": [
                {"node": name, "total_sec": total, "avg_sec": avg}
                for name, total, avg in node_totals
            ],
            "scenarios": all_results,
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    print("\n✅ All scenarios complete!\n")


if __name__ == "__main__":
    run_scenarios()

