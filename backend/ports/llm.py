"""LLM port — what the rest of the app sees."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """A provider that can take a prompt and return parsed JSON."""

    def extract_json(self, prompt: str, max_tokens: int = 8192) -> dict:
        """Run the prompt; return parsed JSON dict. Raises on bad JSON or API error."""
        ...

    def health_check(self) -> tuple[bool, str]:
        """Returns (ok, message). Used by the Test Connection button in the dashboard."""
        ...
