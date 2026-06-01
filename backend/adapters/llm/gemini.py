"""Google Gemini / Gemma adapter (uses the new google-genai SDK)."""
from adapters.llm._utils import parse_json_response


class GeminiAdapter:
    def __init__(self, api_key: str, model: str = "models/gemma-4-31b-it",
                 vision_model: str = "gemini-2.0-flash"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.vision_model = vision_model

    def extract_json(self, prompt: str, max_tokens: int = 8192) -> dict:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"temperature": 0, "max_output_tokens": max_tokens},
        )
        return parse_json_response(response.text)

    def extract_json_from_image(self, image_bytes: bytes, mime_type: str,
                                prompt: str, max_tokens: int = 8192) -> dict:
        from google.genai import types
        response = self._client.models.generate_content(
            model=self.vision_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config={"temperature": 0, "max_output_tokens": max_tokens},
        )
        return parse_json_response(response.text)

    def health_check(self) -> tuple[bool, str]:
        try:
            r = self._client.models.generate_content(
                model=self.model,
                contents="Reply with the single word: ok",
                config={"max_output_tokens": 16, "temperature": 0},
            )
            return True, (r.text or "").strip()[:80]
        except Exception as e:
            return False, str(e)[:200]
