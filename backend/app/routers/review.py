"""Review router — main API endpoints."""
import asyncio
import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..storage.session_store import session_store
from ..services.orchestrator import orchestrator
from ..services.event_bus import event_bus

router = APIRouter(prefix="/api", tags=["review"])


class ReviewRequest(BaseModel):
    source_type: str = "markdown"  # markdown / pdf / tapd
    markdown_content: str = ""
    tapd_workspace: str = ""
    tapd_story_id: str = ""


@router.post("/review/markdown")
async def review_markdown(request: ReviewRequest):
    """Start review from markdown content."""
    if not request.markdown_content:
        raise HTTPException(400, "markdown_content is required")
    job_id = await orchestrator.start_review(
        source_type="markdown",
        file_content=request.markdown_content,
    )
    return {"job_id": job_id}


@router.post("/review/file")
async def review_file(file: UploadFile = File(...)):
    """Start review from uploaded .md or .pdf file."""
    filename = file.filename or ""
    content = await file.read()

    import tempfile, os
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in (".md", ".pdf"):
        raise HTTPException(400, f"Unsupported file type: {suffix}. Only .md and .pdf")

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    source_type = "markdown" if suffix == ".md" else "pdf"
    job_id = await orchestrator.start_review(
        source_type=source_type,
        file_path=tmp_path,
    )
    return {"job_id": job_id}


@router.post("/review/tapd")
async def review_tapd(request: ReviewRequest):
    """Start review from TAPD story."""
    if not request.tapd_workspace or not request.tapd_story_id:
        raise HTTPException(400, "tapd_workspace and tapd_story_id are required")
    job_id = await orchestrator.start_review(
        source_type="tapd",
        tapd_workspace=request.tapd_workspace,
        tapd_story_id=request.tapd_story_id,
    )
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status and report."""
    job = session_store.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    result = {
        "job_id": job["id"],
        "status": job["status"],
        "source_type": job["source_type"],
        "document_title": job.get("document_title"),
        "error": job.get("error"),
        "created_at": job["created_at"],
    }
    if job.get("report_json"):
        result["report"] = json.loads(job["report_json"])
    return result


@router.get("/jobs/{job_id}/events")
async def stream_events(job_id: str):
    """SSE endpoint for real-time progress and thinking trace."""
    job = session_store.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    queue = event_bus.subscribe(job_id)

    async def event_generator():
        try:
            # If job already done, send final state immediately
            if job["status"] == "done" and job.get("report_json"):
                yield f"data: {json.dumps({'type': 'done', 'report': json.loads(job['report_json'])})}\n\n"
                yield "data: {\"type\": \"close\"}\n\n"
                return
            if job["status"] == "failed":
                yield f"data: {json.dumps({'type': 'failed', 'error': job.get('error')})}\n\n"
                yield "data: {\"type\": \"close\"}\n\n"
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event.get("type") in ("done", "failed"):
                        yield "data: {\"type\": \"close\"}\n\n"
                        break
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
        finally:
            event_bus.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{job_id}/trace")
async def get_trace(job_id: str):
    """Get thinking trace for a job."""
    steps = session_store.get_thinking_steps(job_id)
    return {"job_id": job_id, "steps": steps}


@router.get("/jobs")
async def list_jobs(limit: int = 20):
    """List recent jobs."""
    return session_store.list_jobs(limit)
