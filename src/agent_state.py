"""
Agent state model for the Opsfleet LangGraph agent.
Holds shared context as nodes pass data between them.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentState(BaseModel):
    """Shared agent state flowing through the LangGraph pipeline."""

    # Enable legacy flexibility
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    # Input / context
    user_query: Optional[str] = Field(None, description="Original user message")
    intent: Optional[str] = Field(None, description="Detected intent (segment/product/trend/geo)")
    template_id: Optional[str] = Field(None, description="Chosen SQL template ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="Template parameters")

    # Execution phase
    last_sql: Optional[str] = Field(None, description="Rendered SQL text")
    sql: Optional[str] = Field(None, description="Raw/dynamic SQL text")
    dry_run_bytes: Optional[int] = Field(None, description="BigQuery dry-run estimate")
    last_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Preview rows")

    # Output / reasoning
    insights: List[str] = Field(default_factory=list, description="Generated key insights")
    actions: List[str] = Field(default_factory=list, description="Suggested next actions")
    followups: List[str] = Field(default_factory=list, description="Suggested follow-up questions or prompts")
    response: Optional[str] = Field(None, description="Formatted text to print in CLI")
    
    # Cost tracking
    total_llm_cost: float = Field(0.0, description="Cumulative LLM cost for this request in USD")
    llm_calls_count: int = Field(0, description="Number of LLM calls made in this request")

    def get(self, key: str, default=None):
        """Allow dict-like safe access for legacy code."""
        return getattr(self, key, default)
if __name__ == "__main__":
    # quick smoke test
    sample = AgentState(
        user_query="Show me top products this month",
        intent="product",
        template_id="q_top_products",
        params={"start_date": "2025-10-01", "end_date": "2025-10-31"},
    )
    print(sample.model_dump_json(indent=2))
