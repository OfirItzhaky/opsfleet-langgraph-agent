import json

from src.agent_state import AgentState
import src.nodes.plan as plan_router

# try to import defaults from the deterministic module if you split it
try:
    from src.plan_deterministic import DEFAULT_START, DEFAULT_END
except ImportError:
    from src.nodes.plan_deterministic import DEFAULT_START, DEFAULT_END


# ------------------------------------------------------------------
# small helper to force deterministic mode in tests that expect it
# ------------------------------------------------------------------
def _force_deterministic(monkeypatch):
    # plan.py (or src/nodes/plan.py) already imported INTENT_MODE from config,
    # so we patch the module-level variable directly
    monkeypatch.setattr(plan_router, "INTENT_MODE", "deterministic", raising=False)


# ============================================================
# DETERMINISTIC TESTS
# ============================================================

def test_plan_for_segment(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="segment customers", intent="segment")
    out = plan_router.plan_node(s)
    assert out.template_id == "q_customer_segments"
    assert out.params["by"] == "country"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END
    assert out.params["limit"] == 100


def test_plan_for_product(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="top products", intent="product")
    out = plan_router.plan_node(s)
    assert out.template_id == "q_top_products"
    assert out.params["metric"] == "revenue"
    assert out.params["limit"] == 20


def test_plan_for_trend_default(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="sales trend", intent="trend")
    out = plan_router.plan_node(s)
    assert out.template_id == "q_sales_trend"
    assert out.params["grain"] == "month"
    assert out.params["limit"] == 1000


def test_plan_for_geo(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="sales by country", intent="geo")
    out = plan_router.plan_node(s)
    assert out.template_id == "q_geo_sales"
    assert out.params["level"] == "country"
    assert out.params["limit"] == 200


def test_plan_fallback_when_intent_missing(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="just show me something")
    out = plan_router.plan_node(s)
    # falls back to trend
    assert out.template_id == "q_sales_trend"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END


def test_plan_preserves_existing_params(monkeypatch):
    _force_deterministic(monkeypatch)
    s = AgentState(user_query="top products", intent="product", params={"limit": 5})
    out = plan_router.plan_node(s)
    # deterministic_plan does: {**state.params, **params} so 20 wins
    assert out.params["limit"] == 20


# ============================================================
# DETERMINISTIC LLM REFINE
# ============================================================

def test_plan_llm_refine_for_long_query(monkeypatch):
    import src.plan_deterministic as plan_det

    state = AgentState(
        user_query=(
            "show me sales by country for the last 180 days but focus on top "
            "products only and limit to 10 rows please this is long"
        ),
        intent="geo",
    )

    # mock prompt file read
    monkeypatch.setattr(
        plan_det.Path,
        "read_text",
        lambda self, encoding="utf-8": (
            "You may ONLY use these template ids: q_customer_segments, q_top_products, "
            "q_geo_sales, q_sales_trend.\n"
            "User question: {{user_query}}\n"
            "Current template_id: {{template_id}}\n"
            "Current params: {{params}}\n"
        ),
    )

    # fake LLM that returns refined params
    class FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, _):
            from langchain_core.messages import AIMessage
            return AIMessage(
                content=(
                    '{'
                    '"template_id": "q_geo_sales",'
                    '"params": {'
                    '"level": "country",'
                    '"limit": 10,'
                    '"start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)",'
                    '"end_date": "CURRENT_DATE()"'
                    '}'
                    '}'
                )
            )

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(plan_det, "ChatGoogleGenerativeAI", FakeLLM)

    base_template = "q_geo_sales"
    base_params = {"limit": 200}

    new_template, new_params = plan_det._maybe_refine_plan_with_llm(
        state, base_template, base_params
    )

    assert new_template == "q_geo_sales"
    assert new_params["limit"] == 10
    assert new_params["start_date"] == "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)"
    assert new_params["end_date"] == "CURRENT_DATE()"
    assert new_params["level"] == "country"


# ============================================================
# DYNAMIC TESTS
# ============================================================

def test_plan_dynamic_template_mode(monkeypatch):
    """
    CURRENT code in src/plan_dynamic.py only has a success path for SQL.
    So if the LLM returns mode=template (no SQL) → guardrail fails → fallback to trend.
    Test should match that.
    """
    import src.plan_dynamic as plan_dyn

    # mock prompt file read
    monkeypatch.setattr(
        plan_dyn.Path,
        "read_text",
        lambda self, encoding="utf-8": "User: {{user_query}}\nSchema:\n{{schema}}\n",
    )

    # fake LLM to return template JSON (no SQL)
    class FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, _prompt: str):
            class Msg:
                content = json.dumps({
                    "mode": "template",
                    "template_id": "q_geo_sales",
                    "params": {
                        "level": "country",
                        "limit": 123,
                    }
                })
            return Msg()

    monkeypatch.setattr(plan_dyn, "ChatGoogleGenerativeAI", FakeLLM)
    monkeypatch.setattr(plan_dyn, "extract_text", lambda resp: resp.content)
    monkeypatch.setattr(plan_dyn, "strip_code_fences", lambda s: s)

    s = AgentState(user_query="which countries bought the least last week?", intent="geo")
    out = plan_dyn.dynamic_plan(s)

    # because SQL was empty → guardrail failed → fallback
    assert out.template_id == "q_sales_trend"
    assert out.params["locked_template"] is True
    assert out.params["grain"] == "month"


def test_plan_dynamic_sql_mode(monkeypatch):
    """
    This one should succeed because we DO return SQL with LIMIT.
    """
    import src.plan_dynamic as plan_dyn

    # mock prompt file read
    monkeypatch.setattr(
        plan_dyn.Path,
        "read_text",
        lambda self, encoding="utf-8": "User: {{user_query}}\nSchema:\n{{schema}}\n",
    )

    class FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, _prompt: str):
            class Msg:
                content = json.dumps({
                    "mode": "sql",
                    "sql": "SELECT 1 AS x FROM orders LIMIT 10",
                    "reason": "simple test"
                })
            return Msg()

    monkeypatch.setattr(plan_dyn, "ChatGoogleGenerativeAI", FakeLLM)
    monkeypatch.setattr(plan_dyn, "extract_text", lambda resp: resp.content)
    monkeypatch.setattr(plan_dyn, "strip_code_fences", lambda s: s)

    s = AgentState(user_query="ad-hoc query please", intent="geo")
    out = plan_dyn.dynamic_plan(s)

    assert out.template_id == "raw_sql"
    assert out.params["raw_sql"] == "SELECT 1 AS x FROM orders LIMIT 10"
    assert out.params["locked_template"] is True
