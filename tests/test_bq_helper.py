# tests/test_bq_helper.py
import pandas as pd
import pytest
from unittest.mock import MagicMock
from src.clients.bq_helper import BQHelper

def _fake_runner_with_client(fake_client):
    r = type("FakeRunner", (), {})()
    r.client = fake_client
    # execute_query must return a DataFrame since _execute_with_backoff uses it
    r.execute_query = MagicMock(return_value=pd.DataFrame({"x": [1]}))
    return r

def test_dry_run_returns_int():
    fake_client = MagicMock()
    fake_job = MagicMock()
    fake_job.total_bytes_processed = 123456
    fake_client.query.return_value = fake_job

    fake_runner = _fake_runner_with_client(fake_client)
    helper = BQHelper(client=fake_client, runner=fake_runner)  # inject both

    result = helper.dry_run("SELECT 1")
    assert isinstance(result, int)
    assert result == 123456

def test_execute_safe_blocks_large():
    fake_client = MagicMock()
    fake_runner = _fake_runner_with_client(fake_client)

    helper = BQHelper(client=fake_client, runner=fake_runner, max_bytes_scanned=10)
    helper.dry_run = MagicMock(return_value=999999)  # simulate large scan

    with pytest.raises(ValueError):
        helper.execute_safe("SELECT 1")
