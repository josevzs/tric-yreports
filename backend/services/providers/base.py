from abc import ABC, abstractmethod
from backend.models import CategorySuggestion


class BaseAIProvider(ABC):
    @abstractmethod
    async def categorize_batch(
        self,
        expenses: list[dict],
        available_categories: list[str],
        trip_context: str,
    ) -> tuple[list[CategorySuggestion], list[str]]:
        """
        Returns (suggestions, new_categories_proposed).
        suggestions: one per input expense (may reuse entry_id).
        new_categories_proposed: list of newly invented category names.
        """
