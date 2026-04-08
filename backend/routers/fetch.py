import asyncio
import logging
from fastapi import APIRouter, HTTPException

from backend.models import FetchRequest, UploadSummary
from backend.services.tricount_fetcher import fetch_from_tricount
from backend.storage import session_store
from backend.routers.upload import _build_summary

logger = logging.getLogger("tricountreport.fetch")
router = APIRouter()

_FETCH_TIMEOUT = 30.0  # seconds


@router.post("/fetch", response_model=UploadSummary)
async def fetch_registry(body: FetchRequest):
    logger.info("Fetching Tricount registry: %s", body.registry_id)
    try:
        loop = asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, fetch_from_tricount, body.registry_id),
            timeout=_FETCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Tricount fetch timed out after {int(_FETCH_TIMEOUT)}s")
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not connect to Tricount: {e}")
    except Exception as e:
        logger.exception("Failed to fetch registry %s", body.registry_id)
        raise HTTPException(status_code=422, detail=f"Failed to fetch registry '{body.registry_id}': {e}")

    session_id = session_store.create_session(data)
    return _build_summary(session_id, data)
