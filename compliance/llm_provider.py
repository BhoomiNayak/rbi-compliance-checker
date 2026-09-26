"""LLM provider abstraction.

A thin interface so the analyzer never talks to a vendor SDK directly. Gemini is
the default implementation; another provider (e.g. Groq) could be dropped in
later without touching analyzer.py or the pipeline.
"""

from __future__ import annotations

from typing import Protocol

from .config import Config, get_config


class LLMProvider(Protocol):
    """Minimal contract: given a prompt + a Pydantic schema, return JSON text."""

    def generate_json(self, prompt: str, schema: type, *, model: str | None = None) -> str:
        """Return a JSON string constrained to ``schema`` (a Pydantic model class)."""
        ...


class GeminiProvider:
    """Google Gemini implementation using native structured output.

    Uses ``response_mime_type='application/json'`` plus ``response_schema`` so the
    model returns JSON conforming to the given Pydantic model. Gemini guarantees
    JSON shape, not semantics, so callers still validate + apply deterministic
    checks.
    """

    def __init__(self, config: Config | None = None):
        self._config = config or get_config()
        self._config.require_api_key()
        # Imported lazily so the package works without the SDK for offline use.
        from google import genai

        self._client = genai.Client(api_key=self._config.gemini_api_key)

    @property
    def escalation_model(self) -> str:
        return self._config.escalation_model

    def _model_chain(self, model: str | None) -> list[str]:
        """Primary model first, then configured fallbacks (deduped, order kept)."""
        from .config import FALLBACK_MODELS

        chain = [model or self._config.model, *FALLBACK_MODELS]
        seen: set[str] = set()
        return [m for m in chain if not (m in seen or seen.add(m))]

    def _generate_once(self, model: str, prompt: str, schema: type) -> str:
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0.0,
            },
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text

    def generate_json(self, prompt: str, schema: type, *, model: str | None = None) -> str:
        import time

        from google.genai import errors as genai_errors

        last_error: Exception | None = None
        # Try each model in the chain; retry each once on a transient 503.
        for candidate in self._model_chain(model):
            for attempt in range(2):
                try:
                    return self._generate_once(candidate, prompt, schema)
                except genai_errors.ServerError as exc:
                    last_error = exc
                    time.sleep(1.5 * (attempt + 1))
                except genai_errors.ClientError as exc:
                    # 404/permission on this model -> skip to the next candidate.
                    last_error = exc
                    break
        raise RuntimeError(
            f"All Gemini models failed (last error: {last_error})."
        )


def get_provider(config: Config | None = None) -> GeminiProvider:
    """Factory for the default provider."""
    return GeminiProvider(config)
