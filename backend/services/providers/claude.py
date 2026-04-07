import json
from backend.models import CategorySuggestion
from backend.services.providers.base import BaseAIProvider
from backend.services.providers._prompt import build_prompt, parse_response


class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def categorize_batch(
        self,
        expenses: list[dict],
        available_categories: list[str],
        trip_context: str,
    ) -> tuple[list[CategorySuggestion], list[str]]:
        system_prompt, user_prompt = build_prompt(expenses, available_categories, trip_context)
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text
        return parse_response(raw, expenses)
