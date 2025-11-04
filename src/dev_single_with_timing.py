# src/dev_single_with_timing.py
"""
Single-scenario runner with detailed per-node timing.
"""
import time
import sys
from typing import Dict, Any
sys.stdout.reconfigure(line_buffering=True)

from langgraph.graph import StateGraph, END
from src.agent_state import AgentState
from src.nodes.intent import intent_node
from src.nodes.plan import plan_node
from src.nodes.sqlgen import sqlgen_node
from src.nodes.exec import exec_node
from src.nodes.results import results_node
from src.nodes.insight import insight_node
from src.nodes.respond import respond_node


# Global timing storage
node_timings: Dict[str, float] = {}


def timed_wrapper(node_name: str, node_func):
    """Wrapper that times a node execution."""
    def wrapper(state: AgentState, *args, **kwargs) -> AgentState:
        t0 = time.time()
        result = node_func(state, *args, **kwargs)
        elapsed = time.time() - t0
        node_timings[node_name] = elapsed
        print(f"  [{node_name:>8}] {elapsed:>7.3f}s")
        return result
    return wrapper


def build_timed_graph():
    """Build graph with timing instrumentation."""
    sg = StateGraph(AgentState)
    
    # Add nodes with timing wrappers
    sg.add_node("intent", timed_wrapper("intent", intent_node))
    sg.add_node("plan", timed_wrapper("plan", plan_node))
    sg.add_node("sqlgen", timed_wrapper("sqlgen", sqlgen_node))
    sg.add_node("exec", timed_wrapper("exec", exec_node))
    sg.add_node("results", timed_wrapper("results", results_node))
    sg.add_node("insight", timed_wrapper("insight", insight_node))
    sg.add_node("respond", timed_wrapper("respond", respond_node))
    
    # Set up edges
    sg.set_entry_point("intent")
    sg.add_edge("intent", "plan")
    sg.add_edge("plan", "sqlgen")
    sg.add_edge("sqlgen", "exec")
    sg.add_edge("exec", "results")
    sg.add_edge("results", "insight")
    sg.add_edge("insight", "respond")
    sg.add_edge("respond", END)
    
    return sg.compile()


def print_timing_breakdown(total_time: float):
    """Print a nice breakdown of timing."""
    print("\n" + "=" * 80)
    print("TIMING BREAKDOWN")
    print("=" * 80)
    print(f"{'Node':<15} {'Time (s)':>10} {'% of Total':>12} {'Bar':>30}")
    print("-" * 80)
    
    sorted_nodes = sorted(node_timings.items(), key=lambda x: x[1], reverse=True)
    
    for node_name, elapsed in sorted_nodes:
        pct = (elapsed / total_time * 100) if total_time > 0 else 0
        bar_length = int(pct / 2)  # 50% = 25 chars
        bar = "#" * bar_length
        print(f"{node_name:<15} {elapsed:>10.3f} {pct:>11.1f}% {bar}")
    
    print("-" * 80)
    accounted = sum(node_timings.values())
    overhead = total_time - accounted
    overhead_pct = (overhead / total_time * 100) if total_time > 0 else 0
    
    print(f"{'[overhead]':<15} {overhead:>10.3f} {overhead_pct:>11.1f}%")
    print(f"{'TOTAL':<15} {total_time:>10.3f} {'100.0':>11}%")
    print("=" * 80)


def run_single_scenario(query: str):
    """Run a single query with detailed timing."""
    global node_timings
    node_timings = {}  # Reset
    
    print("=" * 80)
    print(f"Query: {query}")
    print("=" * 80)
    print("\nExecuting nodes:")
    
    graph = build_timed_graph()
    
    start_total = time.time()
    
    try:
        result = graph.invoke({"user_query": query})
        elapsed_total = time.time() - start_total
        
        # Print timing breakdown
        print_timing_breakdown(elapsed_total)
        
        print("\n" + "=" * 80)
        print("RESULT SUMMARY")
        print("=" * 80)
        print(f"Intent:   {result.get('intent')}")
        print(f"Template: {result.get('template_id')}")
        
        response = result.get('response', 'No response')
        print(f"\nResponse preview:")
        preview = response[:300] + "..." if len(response) > 300 else response
        print(preview)
        
        # Identify bottleneck
        slowest_node = max(node_timings.items(), key=lambda x: x[1])
        print(f"\n[BOTTLENECK] '{slowest_node[0]}' took {slowest_node[1]:.3f}s ({slowest_node[1]/elapsed_total*100:.1f}% of total)")
        
        return result
        
    except Exception as e:
        elapsed_total = time.time() - start_total
        print(f"\n[ERROR] Failed after {elapsed_total:.3f}s")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test with a simple query
    test_query = "show me the top revenue products from the last 30 days"
    
    print("\n" + "=" * 80)
    print("SINGLE SCENARIO TEST WITH TIMING")
    print("=" * 80 + "\n")
    
    run_single_scenario(test_query)
    
    print("\n[DONE]\n")

