import httpx
from backend.models import CategorySuggestion
from backend.services.providers.base import BaseAIProvider
from backend.services.providers._prompt import build_prompt, parse_response


class OllamaProvider(BaseAIProvider):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def categorize_batch(
        self,
        expenses: list[dict],
        available_categories: list[str],
        trip_context: str,
    ) -> tuple[list[CategorySuggestion], list[str]]:
        system_prompt, user_prompt = build_prompt(expenses, available_categories, trip_context)
        # Ollama /api/chat endpoint
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()

        raw = response.json()["message"]["content"]
        suggestions, new_cats = parse_response(raw, expenses)

        # If parse failed (all uncategorized), retry once with stricter prompt
        failed = all(s.confidence == 0.0 for s in suggestions)
        if failed:
            strict_suffix = "\n\nIMPORTANT: Output ONLY the JSON object. Do not write any text before or after the JSON."
            payload["messages"][-1]["content"] = user_prompt + strict_suffix
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
            raw2 = response.json()["message"]["content"]
            suggestions, new_cats = parse_response(raw2, expenses)

        return suggestions, new_cats
