#!/usr/bin/env python3
"""
Test single query with full logging visible.
"""
import os
os.environ["LOG_FORMAT"] = "console"  # Only console output
os.environ["LOG_LEVEL"] = "INFO"

from src.utils.logging import setup_logging, RequestContext
from src.graph import build_graph

setup_logging()

# Start request tracking
request_id = RequestContext.start_request("show me the top revenue products from the last 30 days")

print("\n" + "="*80)
print("RUNNING QUERY WITH FULL LOGGING")
print("="*80 + "\n")

graph = build_graph()
result = graph.invoke({"user_query": "show me the top revenue products from the last 30 days"})

print("\n" + "="*80)
print("QUERY COMPLETE")
print("="*80)
print(f"\nIntent: {result.get('intent')}")
print(f"Template: {result.get('template_id')}")
print(f"Response length: {len(result.get('response', ''))}")
print(f"\nRequest ID: {request_id}")

RequestContext.clear()

