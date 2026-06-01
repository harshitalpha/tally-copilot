"""OpenAI-compatible adapter — works for OpenAI, vLLM, Text Generation Inference,
Together, Anyscale, Groq, RunPod vLLM endpoints, llama.cpp server, etc.

Configure with base_url + api_key + model. To switch from OpenAI to a self-hosted
vLLM, only change base_url and (usually) model.
"""
from adapters.llm._utils import parse_json_response


class OpenAICompatibleAdapter:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.base_url = base_url

    def extract_json(self, prompt: str, max_tokens: int = 8192) -> dict:
        r = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0,
        )
        return parse_json_response(r.choices[0].message.content)

    def health_check(self) -> tuple[bool, str]:
        try:
            r = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                max_tokens=16,
                temperature=0,
            )
            return True, (r.choices[0].message.content or "").strip()[:80]
        except Exception as e:
            return False, str(e)[:200]
