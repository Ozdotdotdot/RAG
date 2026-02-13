"""Centralized LLM provider factory."""

from __future__ import annotations

import os
from typing import Any


def build_llm(
    provider: str = "ollama",
    model: str | None = None,
    *,
    base_url: str = "http://localhost:11434",
) -> Any:
    """Return a LangChain chat model for the given provider.

    Parameters
    ----------
    provider : str
        "ollama" or "openai".
    model : str | None
        Model name/tag.  Defaults to provider-specific default.
    base_url : str
        Ollama server URL (ignored for openai).
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = model or os.getenv("OPENAI_MODEL", "gpt-5.2")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required when using the openai provider")
        return ChatOpenAI(model=model, temperature=0.1, api_key=api_key)

    # Default: Ollama
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        from langchain_community.chat_models import ChatOllama

    model = model or "qwen3:14b"
    return ChatOllama(model=model, base_url=base_url, temperature=0.1)
