from backend.models import CategorySuggestion
from backend.services.providers.base import BaseAIProvider
from backend.services.providers._prompt import build_prompt, parse_response


class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    async def categorize_batch(
        self,
        expenses: list[dict],
        available_categories: list[str],
        trip_context: str,
    ) -> tuple[list[CategorySuggestion], list[str]]:
        system_prompt, user_prompt = build_prompt(expenses, available_categories, trip_context)
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4096,
        )
        raw = response.choices[0].message.content
        return parse_response(raw, expenses)
