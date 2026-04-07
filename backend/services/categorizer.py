import math
from typing import AsyncGenerator
from backend.models import (
    ParsedData, CategorizationResponse, CategorySuggestion,
    PRESET_CATEGORIES, ProviderSettings, AIProvider,
)
from backend.services.providers.base import BaseAIProvider

CHUNK_SIZE = 15  # expenses per AI call


def get_provider(settings: ProviderSettings) -> BaseAIProvider:
    match settings.provider:
        case AIProvider.CLAUDE:
            from backend.services.providers.claude import ClaudeProvider
            return ClaudeProvider(settings.claude_api_key, settings.claude_model)
        case AIProvider.OPENAI:
            from backend.services.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(settings.openai_api_key, settings.openai_model)
        case AIProvider.OLLAMA:
            from backend.services.providers.ollama import OllamaProvider
            return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    raise ValueError(f"Unknown provider: {settings.provider}")


def _build_context(data: ParsedData) -> tuple[list[dict], str, list[str]]:
    """Returns (expense_dicts, trip_context, available_categories)."""
    members_str = ", ".join(m.member_name for m in data.members)
    dates = [e.date for e in data.expenses if e.date]
    date_range = min(dates).strftime("%B %Y") if dates else "unknown date"
    trip_context = f"Trip in {date_range}. Participants: {members_str}."
    available = PRESET_CATEGORIES + [c for c in data.custom_categories if c not in PRESET_CATEGORIES]
    return trip_context, available


async def categorize_expenses(
    data: ParsedData,
    settings: ProviderSettings,
    entry_ids: list[int] | None = None,
) -> CategorizationResponse:
    """Non-streaming full categorization (used by /categorize endpoint)."""
    chunks_gen = categorize_expenses_streaming(data, settings, entry_ids)
    all_suggestions: list[CategorySuggestion] = []
    all_new_cats: list[str] = []
    async for event in chunks_gen:
        if event["type"] == "result":
            all_suggestions.extend(event["suggestions"])
            for cat in event.get("new_categories", []):
                if cat not in all_new_cats:
                    all_new_cats.append(cat)
    return CategorizationResponse(suggestions=all_suggestions, new_categories_proposed=all_new_cats)


async def categorize_expenses_streaming(
    data: ParsedData,
    settings: ProviderSettings,
    entry_ids: list[int] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Yields dicts:
      {"type": "start", "total": N, "chunks": C}
      {"type": "progress", "completed": N, "total": T, "chunk": i, "chunks": C}
      {"type": "result", "suggestions": [...], "new_categories": [...]}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    if entry_ids is not None:
        target = [e for e in data.expenses if e.entry_id in entry_ids]
    else:
        target = [e for e in data.expenses if e.category == "UNCATEGORIZED"]

    if not target:
        yield {"type": "done"}
        return

    trip_context, available = _build_context(data)
    provider = get_provider(settings)

    # Split into chunks
    chunks = [target[i:i + CHUNK_SIZE] for i in range(0, len(target), CHUNK_SIZE)]
    total = len(target)
    n_chunks = len(chunks)

    yield {"type": "start", "total": total, "chunks": n_chunks}

    completed = 0
    all_suggestions: list[CategorySuggestion] = []
    all_new_cats: list[str] = []

    for i, chunk in enumerate(chunks):
        expense_dicts = [
            {
                "entry_id": e.entry_id,
                "description": e.description,
                "amount": e.amount,
                "currency": e.currency,
                "payer": e.payer,
            }
            for e in chunk
        ]
        try:
            suggestions, new_cats = await provider.categorize_batch(expense_dicts, available, trip_context)
            all_suggestions.extend(suggestions)
            for cat in new_cats:
                if cat not in all_new_cats:
                    all_new_cats.append(cat)
            completed += len(chunk)
            yield {
                "type": "progress",
                "completed": completed,
                "total": total,
                "chunk": i + 1,
                "chunks": n_chunks,
            }
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

    yield {
        "type": "result",
        "suggestions": [s.model_dump() for s in all_suggestions],
        "new_categories": all_new_cats,
    }
    yield {"type": "done"}


async def suggest_categories_for_trip(
    data: ParsedData,
    settings: ProviderSettings,
) -> list[str]:
    """
    Ask AI which of the preset categories are relevant for this trip,
    and whether any new ones are needed.
    Returns a curated ordered list of category names.
    """
    from backend.services.providers._prompt import _CATEGORY_DESCRIPTIONS
    import json

    descriptions = [e.description for e in data.expenses]
    members = [m.member_name for m in data.members]
    dates = [e.date for e in data.expenses if e.date]
    date_range = min(dates).strftime("%B %Y") if dates else "unknown date"

    presets_json = json.dumps({k: v for k, v in _CATEGORY_DESCRIPTIONS.items()}, ensure_ascii=False)

    system_prompt = """You are a travel expense analyst. Given a list of expense descriptions from a trip, suggest which expense categories are relevant.
Return ONLY valid JSON, no explanation."""

    user_prompt = f"""Trip: {date_range}. Participants: {", ".join(members)}.

Expense descriptions:
{json.dumps(descriptions, ensure_ascii=False)}

Available categories (name → description):
{presets_json}

Return JSON:
{{
  "relevant_categories": ["<category name>", ...],
  "new_categories": ["<new name if truly needed>", ...]
}}
Include only categories that are genuinely relevant to these expenses. Order by relevance (most common first)."""

    provider = get_provider(settings)

    # Use the provider's raw capability via the prompt system
    if hasattr(provider, 'client'):
        # Claude or OpenAI
        from backend.models import AIProvider as AP
        from backend.config import load_settings
        s = load_settings()
        if s.provider == AP.CLAUDE:
            msg = provider.client.messages.create(
                model=provider.model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = msg.content[0].text
        else:
            resp = provider.client.chat.completions.create(
                model=provider.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
            )
            raw = resp.choices[0].message.content
    else:
        # Ollama
        import httpx
        payload = {
            "model": provider.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{provider.base_url}/api/chat", json=payload)
            resp.raise_for_status()
        raw = resp.json()["message"]["content"]

    # Parse response
    from backend.services.providers._prompt import _extract_json
    json_str = _extract_json(raw)
    if not json_str:
        return PRESET_CATEGORIES

    try:
        data_resp = json.loads(json_str)
        relevant = data_resp.get("relevant_categories", [])
        new_cats = data_resp.get("new_categories", [])
        # Filter to valid preset names + new ones
        result = [c for c in relevant if c]
        for c in new_cats:
            if c and c not in result:
                result.append(c)
        # Ensure "Otros" is always available
        if "Otros" not in result:
            result.append("Otros")
        return result if result else PRESET_CATEGORIES
    except Exception:
        return PRESET_CATEGORIES
