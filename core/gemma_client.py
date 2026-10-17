from __future__ import annotations

import os

import requests

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:1b"
REQUEST_TIMEOUT_SECONDS = 90
_BODY_SNIPPET_LIMIT = 300


class GemmaClientError(RuntimeError):
    """Raised when the local Ollama/Gemma request cannot be completed."""


def ask_gemma(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise GemmaClientError("prompt must be a non-empty string")

    host = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    url = f"{host}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.Timeout as exc:
        raise GemmaClientError(
            f"Ollama request timed out after {REQUEST_TIMEOUT_SECONDS}s "
            f"(host={host}, model={model})"
        ) from exc
    except requests.ConnectionError as exc:
        raise GemmaClientError(
            f"Could not connect to Ollama at {host}. "
            "Ensure Ollama is installed and running."
        ) from exc
    except requests.RequestException as exc:
        raise GemmaClientError(f"Ollama request failed: {exc}") from exc

    if not response.ok:
        snippet = (response.text or "").strip().replace("\n", " ")
        if len(snippet) > _BODY_SNIPPET_LIMIT:
            snippet = snippet[:_BODY_SNIPPET_LIMIT] + "..."
        detail = f" HTTP body: {snippet}" if snippet else ""
        raise GemmaClientError(
            f"Ollama HTTP error {response.status_code} for model {model} at {url}.{detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise GemmaClientError("Ollama returned a non-JSON response") from exc

    if not isinstance(data, dict):
        raise GemmaClientError("Ollama returned an invalid JSON response")

    message = data.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise GemmaClientError(
            "Ollama response is missing a non-empty message.content field"
        )
    return content
