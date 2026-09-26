"""Configuration: environment, model IDs, and rulebook path.

Loads settings from the environment (via a .env file if present) and exposes a
single ``get_config()`` accessor. Designed so the deterministic engine works with
no API key, while the LLM layer can require one explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# Project root = parent of the ``compliance`` package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULEBOOK = PROJECT_ROOT / "rules" / "rbi_rules.yaml"

# Stable aliases that track the current recommended flash/pro models. Using the
# "-latest" aliases avoids the "no longer available to new users" errors that
# pinned version IDs (e.g. gemini-2.5-flash) can raise on freshly created keys.
DEFAULT_MODEL = "gemini-flash-latest"
DEFAULT_ESCALATION_MODEL = "gemini-pro-latest"

# On transient 503 "high demand" errors the provider falls back through this list
# (in order) so a temporary spike on one model does not fail the whole run.
FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3-flash-preview"]


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    gemini_api_key: str | None
    model: str
    escalation_model: str
    rulebook_path: Path

    @property
    def llm_enabled(self) -> bool:
        """True when an API key is present so LLM analysis can run."""
        return bool(self.gemini_api_key)

    def require_api_key(self) -> str:
        """Return the API key or raise a clear, actionable error."""
        if not self.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your "
                "key (free tier: https://aistudio.google.com/apikey), or set the "
                "GEMINI_API_KEY environment variable. Deterministic checks run "
                "without a key; LLM analysis requires one."
            )
        return self.gemini_api_key


def _get_setting(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment, then Streamlit secrets, then default.

    Locally the value comes from .env (via python-dotenv) or the shell. On
    Streamlit Cloud, secrets are exposed through st.secrets rather than the
    environment, so we fall back to it when available. Wrapped in try/except so
    the config module stays usable outside Streamlit (tests, CLI, eval).
    """
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st  # local import: optional dependency at config time

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # pragma: no cover - streamlit absent or no secrets file
        pass
    return default


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load configuration once and cache it."""
    rulebook = _get_setting("RBI_RULEBOOK_PATH")
    return Config(
        gemini_api_key=_get_setting("GEMINI_API_KEY") or None,
        model=_get_setting("GEMINI_MODEL", DEFAULT_MODEL),
        escalation_model=_get_setting("GEMINI_ESCALATION_MODEL", DEFAULT_ESCALATION_MODEL),
        rulebook_path=Path(rulebook) if rulebook else DEFAULT_RULEBOOK,
    )


def reset_config_cache() -> None:
    """Clear the cached config (used in tests that patch the environment)."""
    get_config.cache_clear()
