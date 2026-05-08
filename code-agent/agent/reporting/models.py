"""Pydantic models for all report data structures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from agent.analysis.logic_errors import LogicFinding
from agent.analysis.vulnerability import VulnFinding


class CoverageRow(BaseModel):
    name: str
    prev_pct: float
    curr_pct: float
    delta: float
    met: bool  # True if curr_pct >= target


class TestGenRow(BaseModel):
    output_path: str
    source_file: str
    methods_added: int
    coverage_before: float
    coverage_after: float


class RunStatus(BaseModel):
    run_date: str
    duration_seconds: float = 0.0
    model: str
    files_scanned: int = 0
    issues: List[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, model: str) -> RunStatus:
        return cls(
            run_date=datetime.now(timezone.utc).isoformat(),
            model=model,
        )

    def add_issue(self, msg: str) -> None:
        self.issues.append(msg)


class HistoryEntry(BaseModel):
    week: str              # "2025-W22"
    run_date: str          # ISO 8601
    java_coverage_pct: float
    python_coverage_pct: float
    high_vulns: int
    medium_vulns: int
    logic_errors: int


class ReportData(BaseModel):
    status: RunStatus
    java_coverage: List[CoverageRow] = Field(default_factory=list)
    python_coverage: List[CoverageRow] = Field(default_factory=list)
    trend_data: List[HistoryEntry] = Field(default_factory=list)
    vuln_findings: List[VulnFinding] = Field(default_factory=list)
    logic_findings: List[LogicFinding] = Field(default_factory=list)
    generated_tests: List[TestGenRow] = Field(default_factory=list)

    def avg_java_coverage(self) -> float:
        if not self.java_coverage:
            return 0.0
        return round(sum(r.curr_pct for r in self.java_coverage) / len(self.java_coverage), 2)

    def avg_python_coverage(self) -> float:
        if not self.python_coverage:
            return 0.0
        return round(sum(r.curr_pct for r in self.python_coverage) / len(self.python_coverage), 2)

    def to_history_entry(self) -> HistoryEntry:
        run_dt = datetime.fromisoformat(self.status.run_date)
        week_str = run_dt.strftime("%G-W%V")
        return HistoryEntry(
            week=week_str,
            run_date=self.status.run_date,
            java_coverage_pct=self.avg_java_coverage(),
            python_coverage_pct=self.avg_python_coverage(),
            high_vulns=sum(1 for f in self.vuln_findings if f.severity == "HIGH"),
            medium_vulns=sum(1 for f in self.vuln_findings if f.severity == "MEDIUM"),
            logic_errors=len(self.logic_findings),
        )
