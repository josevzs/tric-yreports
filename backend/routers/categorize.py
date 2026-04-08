import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger("tricountreport.categorize")

from backend.models import (
    CategorizationRequest, CategorizationResponse,
    ApplyCategorizationRequest, PRESET_CATEGORIES,
)
from backend.config import load_settings
from backend.services.categorizer import categorize_expenses, categorize_expenses_streaming, suggest_categories_for_trip
from backend.storage import session_store

router = APIRouter()


@router.post("/categorize", response_model=CategorizationResponse)
async def run_categorization(body: CategorizationRequest):
    data = session_store.get_session(body.session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = load_settings()
    logger.info("Categorizing %d expenses via %s", len(data.expenses), settings.provider)
    try:
        result = await categorize_expenses(data, settings, body.entry_ids)
    except Exception as e:
        logger.exception("AI categorization failed")
        raise HTTPException(status_code=500, detail=f"AI categorization failed: {e}")

    for cat in result.new_categories_proposed:
        session_store.add_custom_category(body.session_id, cat)

    return result


@router.post("/categorize/stream")
async def stream_categorization(body: CategorizationRequest):
    """SSE endpoint — streams progress events as AI processes expense chunks."""
    data = session_store.get_session(body.session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = load_settings()

    async def generate():
        try:
            async for event in categorize_expenses_streaming(data, settings, body.entry_ids):
                yield f"data: {json.dumps(event)}\n\n"
                # Store new categories as they come in
                if event.get("type") == "result":
                    for cat in event.get("new_categories", []):
                        session_store.add_custom_category(body.session_id, cat)
        except Exception as e:
            logger.exception("SSE categorization error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Ensure the stream is properly terminated even if the client is buffering
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/categorize/apply")
async def apply_categorizations(body: ApplyCategorizationRequest):
    data = session_store.get_session(body.session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    count = session_store.apply_categorizations(body.session_id, body.applications)

    for app in body.applications:
        cat = app.get("category", "")
        if cat and cat not in PRESET_CATEGORIES and cat != "UNCATEGORIZED":
            session_store.add_custom_category(body.session_id, cat)

    return {"applied_count": count}


@router.post("/categories/suggest")
async def suggest_categories(body: CategorizationRequest):
    """Ask AI to suggest which categories are relevant for this trip's expenses."""
    data = session_store.get_session(body.session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = load_settings()
    try:
        suggested = await suggest_categories_for_trip(data, settings)
    except Exception as e:
        # Fallback: return presets
        suggested = PRESET_CATEGORIES

    return {"categories": suggested}
