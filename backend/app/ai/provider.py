"""Pluggable AI layer. Today: NoneProvider (no LLM, templated answer).

To add OpenRouter later:
  1. create app/ai/openrouter.py with a class implementing `generate(question, books) -> str`
     (POST https://openrouter.ai/api/v1/chat/completions with the retrieved books as context)
  2. return it from get_provider() when LMS_AI_PROVIDER=openrouter
Nothing else in the app changes - that's the point of the interface.
"""
from typing import Protocol

from app.config import get_settings


class AIProvider(Protocol):
    name: str

    def generate(self, question: str, books: list) -> str: ...


class NoneProvider:
    name = "none"

    def generate(self, question: str, books: list) -> str:
        if not books:
            return ("I couldn't find books matching that. Try different words, "
                    "a topic like 'history' or 'space', or an author's name.")
        top = ", ".join(f"'{b.title}' by {b.author}" for b in books[:3])
        return f"Here's what matches \"{question}\": {top}. Open a book card to read its description."


def get_provider() -> AIProvider:
    provider = get_settings().ai_provider
    if provider == "none":
        return NoneProvider()
    raise RuntimeError(f"AI provider '{provider}' is not implemented yet (set LMS_AI_PROVIDER=none)")
