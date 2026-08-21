"""Orchestrator — main flow coordination.

State machine: queued → parsing → phase1 → phase2 → aggregating → done/failed
"""
import asyncio
import logging
import uuid
from pathlib import Path

from ..models.document import DocumentModel, SourceType
from ..models.review import (
    JobStatus, AgentPhase1Report, AgentPhase2Report,
    ThinkingStep, AgentPhase1Report as P1R,
)
from ..storage.session_store import session_store
from .agent_runner import AgentRunner
from .context_builder import ContextBuilder
from .doc_parser import DocParser
from .event_bus import event_bus
from .report_aggregator import ReportAggregator
from .tapd_adapter import tapd_adapter

logger = logging.getLogger(__name__)

AGENTS = ["product_manager", "developer", "tester"]
AGENT_LABELS = {
    "product_manager": "产品",
    "developer": "开发",
    "test": "测试",
}


class Orchestrator:
    def __init__(self):
        self._running: set[str] = set()

    async def start_review(
        self,
        source_type: str,
        file_path: str = "",
        file_content: str = "",
        tapd_workspace: str = "",
        tapd_story_id: str = "",
    ) -> str:
        """Create a job and start the review pipeline in background."""
        job_id = str(uuid.uuid4())[:8]
        source_ref = file_path or f"tapd:{tapd_workspace}/{tapd_story_id}"
        session_store.create_job(job_id, source_type, source_ref)

        task = asyncio.create_task(
            self._run_pipeline(
                job_id, source_type, file_path, file_content,
                tapd_workspace, tapd_story_id,
            )
        )
        self._running.add(job_id)
        task.add_done_callback(lambda _: self._running.discard(job_id))
        return job_id

    async def _set_status(self, job_id: str, status: JobStatus, **extra):
        session_store.update_job(job_id, status=status.value, **extra)
        await event_bus.publish(job_id, {
            "type": "status",
            "status": status.value,
            **extra,
        })

    async def _run_pipeline(
        self,
        job_id: str,
        source_type: str,
        file_path: str,
        file_content: str,
        tapd_workspace: str,
        tapd_story_id: str,
    ):
        """Main pipeline — runs in background."""
        try:
            # ─── Stage 1: Parsing ──────────────────────────────────────
            await self._set_status(job_id, JobStatus.parsing)
            document = await self._parse_document(
                source_type, file_path, file_content, tapd_workspace, tapd_story_id
            )
            session_store.update_job(job_id, document_title=document.title)

            # Build context with token budget
            context = ContextBuilder.build_context(document)

            # ─── Stage 2: Phase 1 — 3 agents in parallel ────────────────
            await self._set_status(job_id, JobStatus.phase1)

            async def make_sse_callback(role: str):
                async def cb(step: ThinkingStep):
                    step.agent_role = role
                    session_store.add_thinking_step(
                        job_id, role, step.phase, step.step,
                        step.focus_area, step.raw_output,
                    )
                    await event_bus.publish(job_id, {
                        "type": "thinking",
                        "agent": role,
                        "phase": step.phase,
                        "step": step.step,
                        "focus_area": step.focus_area,
                        "timestamp": step.timestamp,
                    })
                return cb

            phase1_tasks = []
            for role in AGENTS:
                runner = AgentRunner(
                    role=role,
                    document=document,
                    job_id=job_id,
                    sse_callback=await make_sse_callback(role),
                )
                phase1_tasks.append(runner.run_phase1())

            phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)

            phase1_reports: dict[str, AgentPhase1Report] = {}
            for role, result in zip(AGENTS, phase1_results):
                if isinstance(result, Exception):
                    logger.error(f"[{role}] Phase 1 crashed: {result}")
                    phase1_reports[role] = AgentPhase1Report(
                        role=role, verdict=f"该视角审查失败: {result}"
                    )
                    await event_bus.publish(job_id, {
                        "type": "agent_error", "agent": role, "phase": "phase1",
                    })
                else:
                    phase1_reports[role] = result
                    await event_bus.publish(job_id, {
                        "type": "agent_done", "agent": role, "phase": "phase1",
                        "issue_count": len(result.issues),
                        "score": result.overall_score,
                    })

            # ─── Stage 3: Phase 2 — cross review in parallel ────────────
            await self._set_status(job_id, JobStatus.phase2)

            phase2_tasks = []
            for role in AGENTS:
                runner = AgentRunner(
                    role=role,
                    document=document,
                    job_id=job_id,
                    sse_callback=await make_sse_callback(role),
                )
                peers = [phase1_reports[r] for r in AGENTS if r != role]
                phase2_tasks.append(runner.run_phase2(phase1_reports[role], peers))

            phase2_results = await asyncio.gather(*phase2_tasks, return_exceptions=True)

            phase2_reports: dict[str, AgentPhase2Report] = {}
            for role, result in zip(AGENTS, phase2_results):
                if isinstance(result, Exception):
                    logger.error(f"[{role}] Phase 2 crashed: {result}")
                    phase2_reports[role] = AgentPhase2Report(role=role)
                else:
                    phase2_reports[role] = result
                    await event_bus.publish(job_id, {
                        "type": "agent_done", "agent": role, "phase": "phase2",
                        "new_issues": len(result.new_issues),
                    })

            # ─── Stage 4: Aggregation ────────────────────────────────────
            await self._set_status(job_id, JobStatus.aggregating)

            report = ReportAggregator.aggregate(
                job_id=job_id,
                document_title=document.title,
                source_type=source_type,
                phase1_reports=phase1_reports,
                phase2_reports=phase2_reports,
            )

            # ─── Stage 5: Done ───────────────────────────────────────────
            session_store.update_job(
                job_id,
                status=JobStatus.done.value,
                report_json=report.model_dump_json(),
            )
            await event_bus.publish(job_id, {
                "type": "done",
                "report": report.model_dump(),
            })

        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
            session_store.update_job(
                job_id,
                status=JobStatus.failed.value,
                error=str(e),
            )
            await event_bus.publish(job_id, {
                "type": "failed",
                "error": str(e),
            })

    async def _parse_document(
        self, source_type: str, file_path: str, file_content: str,
        tapd_workspace: str, tapd_story_id: str,
    ) -> DocumentModel:
        if source_type == "markdown":
            if file_content:
                return DocParser.parse_markdown(file_content, "上传的Markdown文档")
            return DocParser.parse(file_path)
        elif source_type == "pdf":
            if file_path and Path(file_path).exists():
                return DocParser.parse_pdf(file_path)
            raise ValueError("PDF file path is required")
        elif source_type == "tapd":
            if not tapd_workspace or not tapd_story_id:
                raise ValueError("TAPD workspace_id and story_id are required")
            return await tapd_adapter.fetch_document(tapd_workspace, tapd_story_id)
        else:
            raise ValueError(f"Unknown source type: {source_type}")


orchestrator = Orchestrator()
