import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.models import ReportRequest, ReportResponse
from backend.services.report_generator import generate_markdown, generate_pdf
from backend.storage import session_store

router = APIRouter()


@router.post("/report", response_model=ReportResponse)
async def generate_report(body: ReportRequest):
    data = session_store.get_session(body.session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = ReportResponse()

    if "markdown" in body.formats:
        try:
            result.markdown = generate_markdown(data, body.trip_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Markdown generation failed: {e}")

    if "pdf" in body.formats:
        try:
            pdf_bytes = generate_pdf(data, body.trip_name)
            result.pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    return result


@router.get("/report/download/{session_id}/{format}")
async def download_report(session_id: str, format: str, trip_name: str = "Trip Report"):
    data = session_store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if format == "md":
        content = generate_markdown(data, trip_name)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{trip_name}.md"'},
        )
    elif format == "pdf":
        pdf_bytes = generate_pdf(data, trip_name)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{trip_name}.pdf"'},
        )
    else:
        raise HTTPException(status_code=400, detail="Format must be 'md' or 'pdf'")
