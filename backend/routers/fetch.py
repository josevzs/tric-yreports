import asyncio
import logging
import re
from fastapi import APIRouter, HTTPException, Request

from backend.models import FetchRequest, UploadSummary
from backend.services.tricount_fetcher import fetch_from_tricount
from backend.storage import session_store
from backend.routers.upload import _build_summary
from backend.limiter import limiter

logger = logging.getLogger("easyexpense.fetch")
router = APIRouter()

_FETCH_TIMEOUT = 30.0  # seconds
# Tricount registry IDs are alphanumeric, 6–20 chars (e.g. "tXxXxXxX")
_REGISTRY_ID_RE = re.compile(r'^[A-Za-z0-9_-]{4,40}$')


@router.post("/fetch", response_model=UploadSummary)
@limiter.limit("10/minute")
async def fetch_registry(request: Request, body: FetchRequest):
    # Strip leading URL if the user pasted a full share link
    registry_id = body.registry_id.strip()
    registry_id = re.sub(r'^https?://[^/]+/', '', registry_id).strip('/')

    if not _REGISTRY_ID_RE.match(registry_id):
        raise HTTPException(status_code=400, detail="Invalid registry ID or share link.")

    logger.info("Fetching Tricount registry: %s", registry_id)
    try:
        loop = asyncio.get_event_loop()
        data = await asyncio.wait_for(
            loop.run_in_executor(None, fetch_from_tricount, registry_id),
            timeout=_FETCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Tricount fetch timed out after {int(_FETCH_TIMEOUT)}s. Try again.")
    except ConnectionError:
        raise HTTPException(status_code=502, detail="Could not connect to Tricount. Check the link and try again.")
    except Exception:
        logger.exception("Failed to fetch registry %s", registry_id)
        raise HTTPException(status_code=422, detail="Could not load this Tricount registry. Make sure the link is correct and the registry is public.")

    session_id = session_store.create_session(data)
    return _build_summary(session_id, data)
