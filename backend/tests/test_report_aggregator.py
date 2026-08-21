"""Tests for ReportAggregator."""
from app.models.review import (
    AgentPhase1Report, AgentPhase2Report, Issue, Severity,
    PeerOpinion, SeverityAdjust,
)
from app.services.report_aggregator import ReportAggregator


def make_issue(id: str, severity: Severity, title: str = "test") -> Issue:
    return Issue(
        id=id, severity=severity, location="§1", title=title,
        description="desc", suggestion="sugg",
    )


def test_aggregate_basic():
    p1 = {
        "product_manager": AgentPhase1Report(
            role="product_manager", overall_score=70,
            verdict="OK", highlights=[],
            issues=[make_issue("PM-001", Severity.critical, "critical issue")],
        ),
        "developer": AgentPhase1Report(
            role="developer", overall_score=80,
            verdict="OK", highlights=[],
            issues=[make_issue("DEV-001", Severity.major, "major issue")],
        ),
        "tester": AgentPhase1Report(
            role="tester", overall_score=60,
            verdict="OK", highlights=[],
            issues=[make_issue("TEST-001", Severity.minor, "minor issue")],
        ),
    }
    report = ReportAggregator.aggregate("job1", "Test Doc", "markdown", p1)

    assert report.summary.overall_score == 70
    assert report.summary.severity_counts["critical"] == 1
    assert report.summary.severity_counts["major"] == 1
    assert report.summary.severity_counts["minor"] == 1
    assert "不通过" in report.summary.readiness_verdict
    assert len(report.summary.top_risks) == 2  # critical + major


def test_aggregate_with_phase2():
    p1 = {
        "product_manager": AgentPhase1Report(
            role="product_manager", overall_score=70, verdict="OK",
            highlights=[],
            issues=[make_issue("PM-001", Severity.major)],
        ),
        "developer": AgentPhase1Report(
            role="developer", overall_score=80, verdict="OK",
            highlights=[], issues=[make_issue("DEV-001", Severity.minor)],
        ),
        "tester": AgentPhase1Report(
            role="tester", overall_score=60, verdict="OK",
            highlights=[], issues=[],
        ),
    }
    p2 = {
        "product_manager": AgentPhase2Report(
            role="product_manager",
            peer_agreements=[PeerOpinion(peer_issue_id="DEV-001", comment="认同")],
            peer_disagreements=[],
            new_issues=[make_issue("PM-002", Severity.minor, "new from cross")],
            severity_adjustments=[
                SeverityAdjust(
                    issue_id="PM-001",
                    from_severity=Severity.major,
                    to_severity=Severity.critical,
                    reason="confirmed bigger impact",
                )
            ],
        ),
        "developer": AgentPhase2Report(role="developer"),
        "tester": AgentPhase2Report(role="tester"),
    }
    report = ReportAggregator.aggregate("job1", "Test Doc", "markdown", p1, p2)

    # PM now has 2 issues (PM-001 + PM-002)
    assert report.summary.role_counts["product_manager"] == 2
    # PM-001 severity escalated to critical
    assert report.summary.severity_counts["critical"] == 1
    # Cross summary
    assert report.cross_summary.agreements == 1
    assert report.cross_summary.disagreements == 0


def test_readiness_verdicts():
    def make_reports(counts: dict[str, int]) -> dict:
        issues = []
        for sev, n in counts.items():
            for i in range(n):
                issues.append(make_issue(f"PM-{i}", Severity(sev)))
        return {
            "product_manager": AgentPhase1Report(
                role="product_manager", overall_score=80, verdict="",
                highlights=[], issues=issues,
            ),
            "developer": AgentPhase1Report(
                role="developer", overall_score=80, verdict="", highlights=[], issues=[]),
            "tester": AgentPhase1Report(
                role="tester", overall_score=80, verdict="", highlights=[], issues=[]),
        }

    # No issues → pass
    r = ReportAggregator.aggregate("j", "t", "markdown", make_reports({}))
    assert "通过" in r.summary.readiness_verdict

    # One major → basically pass
    r = ReportAggregator.aggregate("j", "t", "markdown", make_reports({"major": 1}))
    assert "基本通过" in r.summary.readiness_verdict

    # 5 major → conditional pass
    r = ReportAggregator.aggregate("j", "t", "markdown", make_reports({"major": 5}))
    assert "有条件通过" in r.summary.readiness_verdict
