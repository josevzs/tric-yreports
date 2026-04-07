import uuid
from backend.models import ParsedData, Expense

_store: dict[str, ParsedData] = {}


def create_session(data: ParsedData) -> str:
    session_id = str(uuid.uuid4())
    _store[session_id] = data
    return session_id


def get_session(session_id: str) -> ParsedData | None:
    return _store.get(session_id)


def patch_expense_category(session_id: str, entry_id: int, category: str) -> Expense | None:
    data = _store.get(session_id)
    if data is None:
        return None
    for expense in data.expenses:
        if expense.entry_id == entry_id:
            expense.category = category
            return expense
    return None


def add_custom_category(session_id: str, category: str) -> None:
    data = _store.get(session_id)
    if data is None:
        return
    if category not in data.custom_categories:
        data.custom_categories.append(category)


def apply_categorizations(session_id: str, applications: list[dict]) -> int:
    data = _store.get(session_id)
    if data is None:
        return 0
    id_to_expense = {e.entry_id: e for e in data.expenses}
    count = 0
    for app in applications:
        entry_id = app.get("entry_id")
        category = app.get("category")
        if entry_id in id_to_expense and category:
            id_to_expense[entry_id].category = category
            count += 1
    return count
