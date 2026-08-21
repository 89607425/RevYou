"""Report aggregator — merges findings, deduplicates, generates summary."""
from collections import defaultdict
from ..models.review import (
    AgentPhase1Report, AgentPhase2Report, ReviewReport,
    Summary, CrossReviewSummary, Issue, Severity,
)


class ReportAggregator:
    """Aggregates Phase 1 + Phase 2 reports into a final ReviewReport."""

    @staticmethod
    def aggregate(
        job_id: str,
        document_title: str,
        source_type: str,
        phase1_reports: dict[str, AgentPhase1Report],
        phase2_reports: dict[str, AgentPhase2Report] | None = None,
    ) -> ReviewReport:
        # Merge Phase 1 + Phase 2 issues per agent
        all_issues: list[Issue] = []
        role_issue_counts: dict[str, int] = {}
        scores: list[int] = []

        for role, p1 in phase1_reports.items():
            # Combine P1 issues + P2 new issues
            issues = list(p1.issues)
            if phase2_reports and role in phase2_reports:
                p2 = phase2_reports[role]
                issues.extend(p2.new_issues)
                # Apply severity adjustments
                for adj in p2.severity_adjustments:
                    for iss in issues:
                        if iss.id == adj.issue_id:
                            iss.severity = adj.to_severity
                            break

            role_issue_counts[role] = len(issues)
            all_issues.extend(issues)
            if p1.overall_score > 0:
                scores.append(p1.overall_score)

        # Severity counts
        severity_counts: dict[str, int] = defaultdict(int)
        for iss in all_issues:
            severity_counts[iss.severity.value] += 1

        # Top risks: critical + major, sorted by severity then role count
        risk_issues = [
            i for i in all_issues
            if i.severity in (Severity.critical, Severity.major)
        ]
        risk_issues.sort(
            key=lambda x: (
                0 if x.severity == Severity.critical else 1,
                -len(x.description)
            )
        )
        top_risks = risk_issues[:10]

        # Improvement suggestions
        suggestions = [
            f"[{i.id}] {i.title}: {i.suggestion}"
            for i in all_issues
            if i.severity == Severity.suggestion and i.suggestion
        ][:20]

        # Overall score
        overall = int(sum(scores) / len(scores)) if scores else 0

        # Detect agent failures
        failed_agents = [
            role for role, p1 in phase1_reports.items()
            if "失败" in p1.verdict or p1.overall_score == 0
        ]
        critical_count = severity_counts.get("critical", 0)
        major_count = severity_counts.get("major", 0)
        if len(failed_agents) == len(phase1_reports) and phase1_reports:
            readiness = "审查失败 — 所有视角均不可用，请检查 LLM API Key 配置"
        elif failed_agents:
            readiness = (
                f"部分视角不可用（{len(failed_agents)} 个）— "
                "结论仅供参考，建议修复后重新审查"
            )
        # Readiness verdict
        elif critical_count > 0:
            readiness = "不通过 — 存在阻断级问题，需修订后重新评审"
        elif major_count > 3:
            readiness = "有条件通过 — 存在多个高优先级问题，建议修订后通过"
        elif major_count > 0:
            readiness = "基本通过 — 存在高优先级问题，建议跟进修复"
        else:
            readiness = "通过 — 文档质量良好，可进入开发"

        summary = Summary(
            overall_score=overall,
            severity_counts=dict(severity_counts),
            role_counts=role_issue_counts,
            top_risks=top_risks,
            improvement_suggestions=suggestions,
            readiness_verdict=readiness,
        )

        # Cross review summary
        cross_summary = CrossReviewSummary()
        if phase2_reports:
            total_agreements = sum(
                len(p2.peer_agreements) for p2 in phase2_reports.values()
            )
            total_disagreements = sum(
                len(p2.peer_disagreements) for p2 in phase2_reports.values()
            )
            cross_summary.agreements = total_agreements
            cross_summary.disagreements = total_disagreements
            cross_summary.typical_disagreements = [
                f"[{d.peer_issue_id}] {d.reason}"
                for p2 in phase2_reports.values()
                for d in p2.peer_disagreements
            ][:5]

        return ReviewReport(
            job_id=job_id,
            document_title=document_title,
            source_type=source_type,
            summary=summary,
            agents=phase1_reports,
            cross_review=phase2_reports or {},
            cross_summary=cross_summary,
        )
