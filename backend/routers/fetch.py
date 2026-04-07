import asyncio
from fastapi import APIRouter, HTTPException

from backend.models import FetchRequest, UploadSummary
from backend.services.tricount_fetcher import fetch_from_tricount
from backend.storage import session_store
from backend.routers.upload import _build_summary

router = APIRouter()


@router.post("/fetch", response_model=UploadSummary)
async def fetch_registry(body: FetchRequest):
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_from_tricount, body.registry_id)
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not connect to Tricount: {e}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch registry '{body.registry_id}': {e}")

    session_id = session_store.create_session(data)
    return _build_summary(session_id, data)
