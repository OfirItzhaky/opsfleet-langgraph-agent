# tests/test_config.py

import os
import pytest
import importlib


def test_config_loads_minimal_env(monkeypatch):
    # pretend we only have this key
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    # reload to re-evaluate module-level vars
    config = importlib.reload(importlib.import_module("src.config"))

    assert config.GEMINI_API_KEY == "fake-key"
    assert config.GEMINI_MODEL.startswith("gemini-")


def test_require_env_raises_when_missing(monkeypatch):
    # remove from env
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # reload so globals are re-read with empty env
    config = importlib.reload(importlib.import_module("src.config"))

    # extra safety: if your machine still has it somehow,
    # force the module attr to be empty so the function must raise
    config.GEMINI_API_KEY = ""

    with pytest.raises(RuntimeError):
        config.require_env()
