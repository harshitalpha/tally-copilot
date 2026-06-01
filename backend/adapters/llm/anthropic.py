"""Anthropic Claude adapter."""
from adapters.llm._utils import parse_json_response


class AnthropicAdapter:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def extract_json(self, prompt: str, max_tokens: int = 8192) -> dict:
        # Split out a system/user message split if the prompt has a clear "SYSTEM ... \n\nUSER ..." form.
        # The pipeline currently passes the full prompt as one string; we feed it as user content.
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_json_response(response.content[0].text)

    def health_check(self) -> tuple[bool, str]:
        try:
            r = self._client.messages.create(
                model=self.model,
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            )
            return True, (r.content[0].text or "").strip()[:80]
        except Exception as e:
            return False, str(e)[:200]
