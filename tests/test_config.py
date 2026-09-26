import pytest

from compliance import config


def test_defaults_load(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    config.reset_config_cache()
    cfg = config.get_config()
    assert cfg.model == config.DEFAULT_MODEL
    assert cfg.escalation_model == config.DEFAULT_ESCALATION_MODEL
    assert cfg.rulebook_path.name == "rbi_rules.yaml"
    assert cfg.llm_enabled is False


def test_missing_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config.reset_config_cache()
    cfg = config.get_config()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        cfg.require_api_key()


def test_key_present_enables_llm(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    config.reset_config_cache()
    cfg = config.get_config()
    assert cfg.llm_enabled is True
    assert cfg.require_api_key() == "test-key-123"
    config.reset_config_cache()
