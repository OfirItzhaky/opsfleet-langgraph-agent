#!/usr/bin/env python3
"""Test clean logging format with a real query."""
import os
os.environ["LOG_FORMAT"] = "console"
os.environ["LOG_LEVEL"] = "INFO"

from src.utils.logging import setup_logging, RequestContext
from src.graph import build_graph

setup_logging()

print("\n" + "="*80)
print("TESTING CLEAN LOGS WITH REAL QUERY")
print("="*80 + "\n")

# Start request
request_id = RequestContext.start_request("show me the top revenue products from the last 30 days")

# Run query
graph = build_graph()
result = graph.invoke({"user_query": "show me the top revenue products from the last 30 days"})

print("\n" + "="*80)
print("QUERY COMPLETE")
print("="*80)
print(f"\nIntent: {result.get('intent')}")
print(f"Template: {result.get('template_id')}")
print(f"Response length: {len(result.get('response', ''))}")

RequestContext.clear()

