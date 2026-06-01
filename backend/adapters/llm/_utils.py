import json, re


def strip_json_fences(raw: str) -> str:
    """Pull a JSON object out of a possibly-fenced LLM response."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
    return raw.strip("` \n")


def parse_json_response(raw: str) -> dict:
    return json.loads(strip_json_fences(raw))
