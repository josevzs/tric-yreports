from pathlib import Path
import pandas as pd
from datetime import datetime, timezone

from backend.models import ParsedData, Expense, Allocation, Member, Balance


def parse_expense_excel(file_path: str | Path) -> ParsedData:
    with pd.ExcelFile(file_path) as xl:
        sheets = {name: xl.parse(name) for name in xl.sheet_names}

    entries_df = _find_sheet(sheets, ["entries", "entry"])
    allocations_df = _find_sheet(sheets, ["allocations", "allocation"])
    members_df = _find_sheet(sheets, ["members", "member"])
    balances_df = _find_sheet(sheets, ["balances", "balance"])

    expenses = _parse_entries(entries_df)
    allocations = _parse_allocations(allocations_df)
    members = _parse_members(members_df)
    balances = _parse_balances(balances_df)

    return ParsedData(
        expenses=expenses,
        allocations=allocations,
        members=members,
        balances=balances,
    )


def _find_sheet(sheets: dict, candidates: list[str]) -> pd.DataFrame:
    for name, df in sheets.items():
        if name.lower() in candidates:
            return df
    # fallback: return first match by substring
    for name, df in sheets.items():
        for c in candidates:
            if c in name.lower():
                return df
    return pd.DataFrame()


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def _parse_entries(df: pd.DataFrame) -> list[Expense]:
    if df.empty:
        return []
    df = _normalize_cols(df)
    expenses = []
    for _, row in df.iterrows():
        date = _parse_date(row.get("date"))
        if date is None:
            continue
        entry_id = int(row.get("entry_id", row.name))
        amount_raw = row.get("amount", 0)
        amount = _parse_amount(amount_raw)
        category = str(row.get("category", "UNCATEGORIZED"))
        if not category or category == "nan":
            category = "UNCATEGORIZED"
        expenses.append(Expense(
            entry_id=entry_id,
            date=date,
            description=str(row.get("description", "")),
            amount=amount,
            currency=str(row.get("currency", "EUR")),
            payer=str(row.get("payer", "")),
            is_reimbursement=bool(int(row.get("is_reimbursement", 0))),
            category=category,
        ))
    return expenses


def _parse_allocations(df: pd.DataFrame) -> list[Allocation]:
    if df.empty:
        return []
    df = _normalize_cols(df)
    allocations = []
    for _, row in df.iterrows():
        entry_id = int(row.get("entry_id", 0))
        participant = str(row.get("participant", row.get("member_name", "")))
        share = _parse_amount(row.get("share", row.get("amount", 0)))
        currency = str(row.get("currency", "EUR"))
        allocations.append(Allocation(
            entry_id=entry_id,
            participant=participant,
            share=share,
            currency=currency,
        ))
    return allocations


def _parse_members(df: pd.DataFrame) -> list[Member]:
    if df.empty:
        return []
    df = _normalize_cols(df)
    members = []
    for _, row in df.iterrows():
        member_id = int(row.get("member_id", row.name))
        members.append(Member(
            member_id=member_id,
            member_name=str(row.get("member_name", "")),
            status=str(row.get("status", "ACTIVE")),
        ))
    return members


def _parse_balances(df: pd.DataFrame) -> list[Balance]:
    if df.empty:
        return []
    df = _normalize_cols(df)
    balances = []
    for _, row in df.iterrows():
        member = str(row.get("member", row.get("member_name", "")))
        balance = float(row.get("balance", row.get("balance_amount", 0)))
        balances.append(Balance(member=member, balance=balance))
    return balances


def _parse_date(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    # Try Unix timestamp
    try:
        ts = float(value)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        # Sanity check: if year is unreasonably old, try milliseconds
        if dt.year < 2000:
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt
    except (ValueError, OSError, OverflowError):
        pass
    # Try parsing as string
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_amount(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return abs(float(value))
    # Strip currency symbols and parse
    cleaned = str(value).strip()
    cleaned = "".join(c for c in cleaned if c.isdigit() or c in ".-")
    try:
        return abs(float(cleaned))
    except ValueError:
        return 0.0
