"""AgentRunner — the autonomous loop driver.

Plan → Execute → Reflect → Adjust → Consolidate

Each Agent is driven by this runner. The runner calls LLM at each step,
but the Agent's "intelligence" (what to review, when to stop) is decided
by the LLM's reasoning output — not hardcoded logic.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from ..config import settings
from ..models.review import (
    ReviewPlan, ReflectResult, FocusAreaFindings, Issue,
    AgentPhase1Report, AgentPhase2Report, CrossReviewPlan,
    PeerOpinion, SeverityAdjust, ThinkingStep,
)
from ..models.document import DocumentModel
from .llm_client import llm_client
from .prompt_manager import prompt_manager

logger = logging.getLogger(__name__)

# Type for SSE callback: async function that receives a ThinkingStep
SSECallback = Callable[[ThinkingStep], Awaitable[None]]


class AgentRunner:
    """Drives one Agent through the Plan-Execute-Reflect-Adjust-Consolidate loop."""

    ROLES = {
        "product_manager": "pm",
        "developer": "dev",
        "tester": "test",
    }

    def __init__(
        self,
        role: str,
        document: DocumentModel,
        job_id: str = "",
        sse_callback: SSECallback | None = None,
    ):
        self.role = role  # "product_manager" / "developer" / "tester"
        self.role_key = self.ROLES.get(role, role)  # "pm" / "dev" / "test"
        self.document = document
        self.job_id = job_id
        self.sse_callback = sse_callback
        self.call_count = 0
        self.doc_text = document.to_context_text()

    async def _emit(self, step: str, raw_output: str, focus_area: str = "", phase: str = "phase1"):
        """Push a thinking step to SSE and return the step."""
        ts = ThinkingStep(
            agent_role=self.role,
            phase=phase,
            step=step,
            focus_area=focus_area,
            raw_output=raw_output,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if self.sse_callback:
            await self.sse_callback(ts)
        return ts

    async def _llm_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Call LLM and return parsed JSON. Increments call counter."""
        self.call_count += 1
        return await llm_client.complete_json(system_prompt, user_prompt)

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: Independent Review Loop
    # ═══════════════════════════════════════════════════════════════════

    async def run_phase1(self) -> AgentPhase1Report:
        """Execute the full Phase 1 autonomous loop."""
        try:
            # ─── Step 1: Plan ────────────────────────────────────────────
            sys_prompt, user_prompt = prompt_manager.get_phase1_plan(
                self.role_key, self.doc_text
            )
            plan_data = await self._llm_json(sys_prompt, user_prompt)
            review_plan = ReviewPlan(**plan_data)
            await self._emit("plan", json.dumps(plan_data, ensure_ascii=False))

            logger.info(
                f"[{self.role}] Plan: {len(review_plan.focus_areas)} focus areas, "
                f"depth={review_plan.depth_assessment}"
            )

            # ─── Step 2: Execute (parallel across focus areas) ───────────
            all_findings: list[FocusAreaFindings] = []

            if review_plan.depth_assessment == 1 and review_plan.focus_areas:
                # Single pass: batch all areas into one call (cost optimization)
                all_findings = await self._execute_batch(review_plan)
            else:
                # Multi-area parallel execution
                execute_tasks = [
                    self._execute_focus_area(fa, review_plan)
                    for fa in review_plan.focus_areas
                ]
                results = await asyncio.gather(*execute_tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning(f"[{self.role}] Execute failed: {r}")
                        all_findings.append(FocusAreaFindings(
                            area="error", issues=[], notes=str(r)
                        ))
                    elif r:
                        all_findings.append(r)

            # ─── Steps 3-4: Reflect → Adjust loop ────────────────────────
            reflect_loops = 0
            reflect_result = await self._reflect(review_plan, all_findings, reflect_loops)

            while (reflect_result.needs_another_pass
                   and reflect_loops < settings.max_reflect_loops
                   and self.call_count < settings.max_llm_calls_per_agent):
                # Adjust: re-execute on gap areas
                gap_findings = await self._adjust(
                    review_plan, reflect_result, all_findings
                )
                all_findings.extend(gap_findings)
                reflect_loops += 1
                reflect_result = await self._reflect(review_plan, all_findings, reflect_loops)

            # ─── Step 5: Consolidate ──────────────────────────────────────
            if self.call_count >= settings.max_llm_calls_per_agent:
                logger.warning(f"[{self.role}] Hit call limit, forcing consolidate")

            report = await self._consolidate(all_findings, reflect_result)

            # Attach thinking trace
            report.review_plan = review_plan
            report.reflect_result = reflect_result
            report.call_count = self.call_count

            logger.info(
                f"[{self.role}] Phase 1 done: {len(report.issues)} issues, "
                f"score={report.overall_score}, calls={self.call_count}"
            )
            return report

        except Exception as e:
            logger.error(f"[{self.role}] Phase 1 failed: {e}", exc_info=True)
            return AgentPhase1Report(
                role=self.role,
                overall_score=0,
                verdict=f"该视角审查失败: {str(e)}",
                highlights=[],
                issues=[],
                call_count=self.call_count,
            )

    async def _execute_focus_area(self, fa, review_plan: ReviewPlan) -> FocusAreaFindings:
        """Execute review on one focus area."""
        if self.call_count >= settings.max_llm_calls_per_agent:
            return FocusAreaFindings(area=fa.area, issues=[], notes="call limit reached")

        fa_str = json.dumps({
            "area": fa.area,
            "questions": fa.questions,
            "related_sections": fa.related_sections,
        }, ensure_ascii=False)
        plan_str = json.dumps(review_plan.model_dump(), ensure_ascii=False)

        sys_prompt, user_prompt = prompt_manager.get_phase1_execute(
            self.role_key, self.doc_text, plan_str, fa_str
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("execute", json.dumps(data, ensure_ascii=False), fa.area)

        issues = [Issue(**i) for i in data.get("issues", [])]
        return FocusAreaFindings(
            area=data.get("area", fa.area),
            issues=issues,
            notes=data.get("notes", "")
        )

    async def _execute_batch(self, review_plan: ReviewPlan) -> list[FocusAreaFindings]:
        """Execute all focus areas in a single LLM call (depth=1 optimization)."""
        all_areas = json.dumps(
            [fa.model_dump() for fa in review_plan.focus_areas],
            ensure_ascii=False
        )
        plan_str = json.dumps(review_plan.model_dump(), ensure_ascii=False)

        sys_prompt, user_prompt = prompt_manager.get_phase1_execute(
            self.role_key, self.doc_text, plan_str, all_areas
        )
        data = await self._llm_json(sys_prompt, user_prompt)

        # Response may be a list or a single object
        if isinstance(data, list):
            results = []
            for item in data:
                await self._emit("execute", json.dumps(item, ensure_ascii=False),
                                 item.get("area", ""))
                issues = [Issue(**i) for i in item.get("issues", [])]
                results.append(FocusAreaFindings(
                    area=item.get("area", ""),
                    issues=issues,
                    notes=item.get("notes", "")
                ))
            return results
        else:
            await self._emit("execute", json.dumps(data, ensure_ascii=False),
                             data.get("area", ""))
            issues = [Issue(**i) for i in data.get("issues", [])]
            return [FocusAreaFindings(
                area=data.get("area", "all"),
                issues=issues,
                notes=data.get("notes", "")
            )]

    async def _reflect(self, review_plan: ReviewPlan,
                        all_findings: list[FocusAreaFindings],
                        loop_num: int) -> ReflectResult:
        """Self-assessment step."""
        plan_str = json.dumps(review_plan.model_dump(), ensure_ascii=False)
        findings_str = json.dumps(
            [f.model_dump() for f in all_findings], ensure_ascii=False
        )

        sys_prompt, user_prompt = prompt_manager.get_phase1_reflect(
            self.role_key, plan_str, findings_str
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("reflect", json.dumps(data, ensure_ascii=False),
                         phase="phase1")

        result = ReflectResult(**data)
        logger.info(
            f"[{self.role}] Reflect (loop {loop_num}): "
            f"needs_another_pass={result.needs_another_pass}, "
            f"gaps={len(result.coverage_gaps)}"
        )
        return result

    async def _adjust(self, review_plan: ReviewPlan,
                      reflect_result: ReflectResult,
                      all_findings: list[FocusAreaFindings]) -> list[FocusAreaFindings]:
        """Adjustment step — re-execute on gap areas."""
        gap_findings = []
        for gap_area in reflect_result.gap_areas:
            if self.call_count >= settings.max_llm_calls_per_agent:
                break
            fa = type("FA", (), {"area": gap_area, "questions": [],
                                 "related_sections": []})()
            finding = await self._execute_focus_area(fa, review_plan)
            gap_findings.append(finding)
            await self._emit("adjust", json.dumps(finding.model_dump(), ensure_ascii=False),
                             gap_area, "phase1")
        return gap_findings

    async def _consolidate(self, all_findings: list[FocusAreaFindings],
                           reflect_result: ReflectResult) -> AgentPhase1Report:
        """Consolidation step — produce final report."""
        findings_str = json.dumps(
            [f.model_dump() for f in all_findings], ensure_ascii=False
        )
        reflect_str = json.dumps(reflect_result.model_dump(), ensure_ascii=False)

        sys_prompt, user_prompt = prompt_manager.get_phase1_consolidate(
            self.role_key, findings_str, reflect_str
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("consolidate", json.dumps(data, ensure_ascii=False), "phase1")

        # Remove false positives
        fp_ids = set(reflect_result.false_positives)
        issues = [Issue(**i) for i in data.get("issues", [])
                  if i.get("id", "") not in fp_ids]

        return AgentPhase1Report(
            role=self.role,
            overall_score=data.get("overall_score", 0),
            verdict=data.get("verdict", ""),
            highlights=data.get("highlights", []),
            issues=issues,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: Cross-Review Loop
    # ═══════════════════════════════════════════════════════════════════

    async def run_phase2(self, my_phase1: AgentPhase1Report,
                         peer_reports: list[AgentPhase1Report]) -> AgentPhase2Report:
        """Execute the Phase 2 cross-review autonomous loop."""
        try:
            self.call_count = 0  # Reset for Phase 2

            my_p1_str = json.dumps(my_phase1.model_dump(), ensure_ascii=False)
            peer_str = json.dumps(
                [r.model_dump() for r in peer_reports], ensure_ascii=False
            )

            # ─── Step 1: Cross Plan ──────────────────────────────────────
            sys_prompt, user_prompt = prompt_manager.get_phase2_plan(
                self.role_key, self.doc_text, my_p1_str, peer_str
            )
            plan_data = await self._llm_json(sys_prompt, user_prompt)
            cross_plan = CrossReviewPlan(**plan_data)
            await self._emit("plan", json.dumps(plan_data, ensure_ascii=False), "", "phase2")

            # Fallback: if LLM produced no re_review_targets, auto-populate
            # from peer findings so the cross-review chain doesn't run empty
            if not cross_plan.re_review_targets:
                my_locations = {
                    iss.location for iss in my_phase1.issues if iss.location
                }
                peer_locations: list[str] = []
                seen: set[str] = set()
                for peer in peer_reports:
                    for iss in peer.issues:
                        loc = iss.location or ""
                        if loc and loc not in my_locations and loc not in seen:
                            seen.add(loc)
                            peer_locations.append(loc)
                if peer_locations:
                    cross_plan.re_review_targets = peer_locations[:5]
                else:
                    cross_plan.re_review_targets = ["评估所有同行发现：给出认同或异议"]
                logger.info(
                    f"[{self.role}] Cross plan: LLM produced 0 targets, "
                    f"auto-populated {len(cross_plan.re_review_targets)} from peer findings"
                )
            else:
                logger.info(
                    f"[{self.role}] Cross plan: {len(cross_plan.re_review_targets)} targets"
                )

            # ─── Step 2: Execute cross-review (parallel) ──────────────────
            cross_findings = []
            execute_tasks = []
            for target in cross_plan.re_review_targets:
                if self.call_count >= settings.max_llm_calls_per_agent:
                    break
                execute_tasks.append(
                    self._execute_cross(target, cross_plan, peer_str)
                )

            if execute_tasks:
                results = await asyncio.gather(*execute_tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning(f"[{self.role}] Cross execute failed: {r}")
                    elif r:
                        cross_findings.append(r)

            # ─── Steps 3-4: Reflect → Adjust ─────────────────────────────
            reflect_loops = 0
            reflect_result = await self._cross_reflect(cross_plan, cross_findings)

            while (reflect_result.needs_another_pass
                   and reflect_loops < settings.max_reflect_loops
                   and self.call_count < settings.max_llm_calls_per_agent):
                for gap in reflect_result.gap_areas:
                    if self.call_count >= settings.max_llm_calls_per_agent:
                        break
                    finding = await self._execute_cross(gap, cross_plan, peer_str)
                    cross_findings.append(finding)
                reflect_loops += 1
                reflect_result = await self._cross_reflect(cross_plan, cross_findings)

            # ─── Step 5: Consolidate ──────────────────────────────────────
            report = await self._cross_consolidate(cross_findings, reflect_result)
            report.cross_review_plan = cross_plan
            report.call_count = self.call_count

            logger.info(
                f"[{self.role}] Phase 2 done: {len(report.new_issues)} new, "
                f"{len(report.peer_agreements)} agreements, "
                f"{len(report.peer_disagreements)} disagreements, "
                f"calls={self.call_count}"
            )
            return report

        except Exception as e:
            logger.error(f"[{self.role}] Phase 2 failed: {e}", exc_info=True)
            return AgentPhase2Report(role=self.role, call_count=self.call_count)

    async def _execute_cross(self, target: str, cross_plan: CrossReviewPlan,
                              peer_str: str) -> dict:
        """Execute cross-review on one target area."""
        plan_str = json.dumps(cross_plan.model_dump(), ensure_ascii=False)
        sys_prompt, user_prompt = prompt_manager.get_phase2_execute(
            self.role_key, self.doc_text, plan_str, peer_str, target
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("execute", json.dumps(data, ensure_ascii=False), target, "phase2")
        return data

    async def _cross_reflect(self, cross_plan: CrossReviewPlan,
                              cross_findings: list[dict]) -> ReflectResult:
        plan_str = json.dumps(cross_plan.model_dump(), ensure_ascii=False)
        findings_str = json.dumps(cross_findings, ensure_ascii=False)
        sys_prompt, user_prompt = prompt_manager.get_phase2_reflect(
            self.role_key, plan_str, findings_str
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("reflect", json.dumps(data, ensure_ascii=False), "", "phase2")
        return ReflectResult(**data)

    async def _cross_consolidate(self, cross_findings: list[dict],
                                  reflect_result: ReflectResult) -> AgentPhase2Report:
        # Pre-extract peer opinions from execute results so they survive
        # even if the consolidate LLM drops them
        pre_agreements: dict[str, PeerOpinion] = {}
        pre_disagreements: dict[str, PeerOpinion] = {}
        pre_new_issues_raw: list[dict] = []
        pre_adjustments: dict[str, dict] = {}

        for f in cross_findings:
            for op in f.get("peer_opinions", []):
                pid = op.get("peer_issue_id", "")
                if not pid:
                    continue
                if op.get("type") == "agreement" and pid not in pre_agreements:
                    pre_agreements[pid] = PeerOpinion(
                        peer_issue_id=pid, comment=op.get("comment", "")
                    )
                elif op.get("type") == "disagreement" and pid not in pre_disagreements:
                    pre_disagreements[pid] = PeerOpinion(
                        peer_issue_id=pid, comment=op.get("comment", "")
                    )
            for adj in f.get("severity_adjustments", []):
                iid = adj.get("issue_id", "")
                if iid and iid not in pre_adjustments:
                    pre_adjustments[iid] = adj
            for iss in f.get("new_issues", []):
                pre_new_issues_raw.append(iss)

        findings_str = json.dumps(cross_findings, ensure_ascii=False)
        reflect_str = json.dumps(reflect_result.model_dump(), ensure_ascii=False)
        sys_prompt, user_prompt = prompt_manager.get_phase2_consolidate(
            self.role_key, findings_str, reflect_str
        )
        data = await self._llm_json(sys_prompt, user_prompt)
        await self._emit("consolidate", json.dumps(data, ensure_ascii=False), "", "phase2")

        fp_ids = set(reflect_result.false_positives)

        # New issues: prefer LLM output (it deduplicates), fallback to pre-extracted
        llm_new_issues = [Issue(**i) for i in data.get("new_issues", [])
                          if i.get("id", "") not in fp_ids]
        if llm_new_issues:
            new_issues = llm_new_issues
        else:
            new_issues = [Issue(**i) for i in pre_new_issues_raw
                          if i.get("id", "") not in fp_ids]

        # Agreements: use LLM output if non-empty, else pre-extracted
        llm_agreements = [PeerOpinion(**p) for p in data.get("peer_agreements", [])]
        agreements = llm_agreements if llm_agreements else list(pre_agreements.values())

        # Disagreements: same fallback
        llm_disagreements = [PeerOpinion(**p) for p in data.get("peer_disagreements", [])]
        disagreements = llm_disagreements if llm_disagreements else list(pre_disagreements.values())

        # Adjustments: same fallback (remap from/to → from_severity/to_severity)
        def _parse_adj(adj: dict) -> SeverityAdjust:
            return SeverityAdjust(
                issue_id=adj.get("issue_id", ""),
                from_severity=adj.get("from", adj.get("from_severity", "major")),
                to_severity=adj.get("to", adj.get("to_severity", "major")),
                reason=adj.get("reason", ""),
            )
        llm_adjustments = [_parse_adj(s) for s in data.get("severity_adjustments", [])]
        if llm_adjustments:
            severity_adjustments = llm_adjustments
        else:
            severity_adjustments = [_parse_adj(a) for a in pre_adjustments.values()]

        return AgentPhase2Report(
            role=self.role,
            peer_agreements=agreements,
            peer_disagreements=disagreements,
            new_issues=new_issues,
            severity_adjustments=severity_adjustments,
        )
