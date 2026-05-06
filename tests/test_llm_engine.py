import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_review_api.core.models import FieldCandidate
from contract_review_api.services import llm_engine


def test_real_mode_missing_env_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    out = llm_engine.run_llm_review_with_debug(
        [FieldCandidate(field_key="project_name", value="x", confidence=0.7)],
        user_position=None,
    )
    assert out["fallback_reason"] == "missing_llm_env"
    assert len(out["issues"]) == 1


def test_real_mode_invalid_json_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234")
    monkeypatch.setenv("LLM_MODEL", "demo-model")

    def _fake_call(*args, **kwargs):
        return "not-a-json-array"

    monkeypatch.setattr(llm_engine, "_call_real_model", _fake_call)
    out = llm_engine.run_llm_review_with_debug(
        [FieldCandidate(field_key="project_name", value="x", confidence=0.7)],
        user_position=None,
    )
    assert out["fallback_reason"] == "invalid_or_empty_json"
    assert len(out["issues"]) == 1


def test_real_mode_timeout_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234")
    monkeypatch.setenv("LLM_MODEL", "demo-model")

    def _fake_call(*args, **kwargs):
        raise TimeoutError("boom")

    monkeypatch.setattr(llm_engine, "_call_real_model", _fake_call)
    out = llm_engine.run_llm_review_with_debug(
        [FieldCandidate(field_key="project_name", value="x", confidence=0.7)],
        user_position=None,
    )
    assert out["fallback_reason"] == "timeout"
    assert len(out["issues"]) == 1
