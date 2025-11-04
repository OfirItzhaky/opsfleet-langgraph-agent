from src.nodes.exec import exec_node
from src.agent_state import AgentState


class FakeBQ:
    def __init__(self):
        self.dry_run_called = False
        self.execute_called = False

    def dry_run(self, sql: str) -> int:
        self.dry_run_called = True
        assert "select" in sql.lower()
        return 12345

    def execute(self, sql: str, max_rows: int = 50):
        self.execute_called = True
        rows = [
            {"country": "USA", "revenue": 100.0},
            {"country": "Israel", "revenue": 80.0},
        ]
        total_rows = 2
        return rows, total_rows


def test_exec_happy_path():
    s = AgentState(last_sql="SELECT * FROM table")
    fake = FakeBQ()
    out = exec_node(s, bq=fake)

    assert out.dry_run_bytes == 12345
    assert len(out.last_results) == 2
    assert out.params.get("rowcount") == 2
    assert fake.dry_run_called
    assert fake.execute_called


def test_exec_missing_sql_raises():
    s = AgentState()
    try:
        exec_node(s, bq=FakeBQ())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_exec_dry_run_failure_does_not_crash():
    class BadBQ(FakeBQ):
        def dry_run(self, sql: str) -> int:
            raise RuntimeError("dry-run error")

    s = AgentState(last_sql="SELECT 1")
    out = exec_node(s, bq=BadBQ())
    assert out.dry_run_bytes is None
    assert "dry_run_failed" in out.params.get("exec_error", "")
