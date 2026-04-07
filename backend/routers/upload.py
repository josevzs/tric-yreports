import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.models import UploadSummary
from backend.services.excel_parser import parse_tricount_excel
from backend.storage import session_store

router = APIRouter()


@router.post("/upload", response_model=UploadSummary)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        data = parse_tricount_excel(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel file: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    session_id = session_store.create_session(data)
    return _build_summary(session_id, data)


def _build_summary(session_id: str, data) -> UploadSummary:
    from backend.models import UploadSummary
    dates = [e.date for e in data.expenses if e.date]
    date_from = min(dates).strftime("%Y-%m-%d") if dates else ""
    date_to = max(dates).strftime("%Y-%m-%d") if dates else ""
    total = sum(e.amount for e in data.expenses if not e.is_reimbursement)
    currencies = {e.currency for e in data.expenses}
    currency = next(iter(currencies)) if len(currencies) == 1 else "mixed"
    return UploadSummary(
        session_id=session_id,
        expense_count=len(data.expenses),
        member_count=len(data.members),
        date_from=date_from,
        date_to=date_to,
        total_amount=round(total, 2),
        currency=currency,
    )
