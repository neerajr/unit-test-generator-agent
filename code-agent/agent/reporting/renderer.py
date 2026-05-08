"""Jinja2 HTML + WeasyPrint PDF report renderer."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import weasyprint
from jinja2 import Environment, FileSystemLoader

from agent.reporting.models import HistoryEntry, ReportData

if TYPE_CHECKING:
    from agent.config import AgentConfig

LOG = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _build_svg_trend(entries: list[HistoryEntry]) -> str:
    """Generate an inline SVG line chart from the last 4 history entries."""
    recent = entries[-4:] if len(entries) >= 4 else entries
    if not recent:
        return '<svg width="400" height="60"><text x="10" y="30" font-size="12" fill="#888">No trend data yet.</text></svg>'

    width, height = 400, 160
    pad_left, pad_right, pad_top, pad_bottom = 40, 20, 20, 30

    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    n = len(recent)

    def x_pos(i: int) -> float:
        return pad_left + (i / max(n - 1, 1)) * chart_w

    def y_pos(pct: float) -> float:
        # Clamp to [0,100], map to chart coords (top=100%, bottom=0%)
        clamped = max(0.0, min(100.0, pct))
        return pad_top + (1.0 - clamped / 100.0) * chart_h

    def polyline_points(values: list[float]) -> str:
        return " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in enumerate(values))

    java_vals = [e.java_coverage_pct for e in recent]
    py_vals = [e.python_coverage_pct for e in recent]
    labels = [e.week for e in recent]

    # Grid line at 90% (target)
    y90 = y_pos(90.0)

    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="sans-serif" font-size="11">',
        # background
        f'<rect width="{width}" height="{height}" fill="#f8f9fa" rx="4"/>',
        # 90% target dashed line
        f'<line x1="{pad_left}" y1="{y90:.1f}" x2="{width - pad_right}" y2="{y90:.1f}" '
        f'stroke="#dc3545" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>',
        f'<text x="{pad_left - 3}" y="{y90 + 4:.1f}" text-anchor="end" fill="#dc3545" font-size="9">90%</text>',
        # Java line (blue)
        f'<polyline points="{polyline_points(java_vals)}" fill="none" stroke="#0d6efd" stroke-width="2"/>',
        # Python line (green)
        f'<polyline points="{polyline_points(py_vals)}" fill="none" stroke="#198754" stroke-width="2"/>',
    ]

    # Dots and labels
    for i, entry in enumerate(recent):
        xp = x_pos(i)
        svg_parts.append(f'<circle cx="{xp:.1f}" cy="{y_pos(java_vals[i]):.1f}" r="3" fill="#0d6efd"/>')
        svg_parts.append(f'<circle cx="{xp:.1f}" cy="{y_pos(py_vals[i]):.1f}" r="3" fill="#198754"/>')
        svg_parts.append(
            f'<text x="{xp:.1f}" y="{height - 5}" text-anchor="middle" fill="#555">{labels[i]}</text>'
        )

    # Legend
    lx, ly = pad_left, pad_top - 6
    svg_parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx + 16}" y2="{ly}" stroke="#0d6efd" stroke-width="2"/>')
    svg_parts.append(f'<text x="{lx + 20}" y="{ly + 4}" fill="#0d6efd">Java</text>')
    svg_parts.append(f'<line x1="{lx + 70}" y1="{ly}" x2="{lx + 86}" y2="{ly}" stroke="#198754" stroke-width="2"/>')
    svg_parts.append(f'<text x="{lx + 90}" y="{ly + 4}" fill="#198754">Python</text>')

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _load_history(reports_dir: Path) -> list[HistoryEntry]:
    history_path = reports_dir / "run_history.json"
    if not history_path.exists():
        return []
    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
        return [HistoryEntry(**e) for e in raw]
    except Exception as exc:
        LOG.warning("Could not load run_history.json: %s", exc)
        return []


def _save_history(reports_dir: Path, entries: list[HistoryEntry]) -> None:
    history_path = reports_dir / "run_history.json"
    data = [e.model_dump() for e in entries]
    # Write atomically: temp file + rename
    tmp = history_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(history_path)
    except Exception as exc:
        LOG.error("Failed to save run_history.json: %s", exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def render_report(
    data: ReportData,
    config: AgentConfig,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Render HTML and PDF reports. Returns (html_path, pdf_path)."""
    reports_dir = config.output.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Determine week filename
    run_dt = datetime.fromisoformat(data.status.run_date)
    week_label = run_dt.strftime("%Y-W%V")
    html_path = reports_dir / f"{week_label}-report.html"
    pdf_path = reports_dir / f"{week_label}-report.pdf"

    # Load and update history
    history = _load_history(reports_dir)
    new_entry = data.to_history_entry()
    history = [e for e in history if e.week != new_entry.week]  # replace same week
    history.append(new_entry)
    data.trend_data = history

    # Sort coverage tables: worst delta first
    data.java_coverage.sort(key=lambda r: r.delta)
    data.python_coverage.sort(key=lambda r: r.delta)

    # Sort vulnerability findings: HIGH first
    _sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    data.vuln_findings.sort(key=lambda f: _sev_order.get(f.severity, 4))
    data.logic_findings.sort(key=lambda f: _sev_order.get(f.severity, 4))

    trend_svg = _build_svg_trend(history)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")

    html_content = template.render(
        data=data,
        trend_svg=trend_svg,
        report_date=run_dt.strftime("%Y-%m-%d %H:%M UTC"),
        week_label=week_label,
        target_pct=config.coverage.target_pct,
    )

    if dry_run:
        LOG.info("[dry-run] Would write report to %s and %s", html_path, pdf_path)
        return html_path, pdf_path

    html_path.write_text(html_content, encoding="utf-8")
    LOG.info("Wrote HTML report: %s", html_path)

    try:
        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        LOG.info("Wrote PDF report: %s", pdf_path)
    except Exception as exc:
        msg = f"PDF generation failed: {exc}"
        LOG.error(msg, exc_info=True)
        data.status.add_issue(msg)

    _save_history(reports_dir, history)
    LOG.info("Updated run_history.json")

    return html_path, pdf_path


if __name__ == "__main__":
    import sys
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from agent.config import get_config
    from agent.reporting.models import (
        CoverageRow,
        ReportData,
        RunStatus,
        TestGenRow,
    )
    from agent.analysis.vulnerability import VulnFinding
    from agent.analysis.logic_errors import LogicFinding

    cfg = get_config()

    rs = RunStatus.empty(cfg.llm.model)
    rs.files_scanned = 42
    rs.duration_seconds = 123.4
    rs.add_issue("Semgrep rules dir is empty — skipped")

    report_data = ReportData(
        status=rs,
        java_coverage=[
            CoverageRow(name="com.example.UserService", prev_pct=72.0, curr_pct=88.5, delta=16.5, met=False),
            CoverageRow(name="com.example.OrderService", prev_pct=95.0, curr_pct=95.0, delta=0.0, met=True),
        ],
        python_coverage=[
            CoverageRow(name="app/routers/items.py", prev_pct=60.0, curr_pct=91.0, delta=31.0, met=True),
        ],
        vuln_findings=[
            VulnFinding(tool="Bandit", severity="HIGH", category="hardcoded_password",
                       file="app/config.py", line=15, description="Hardcoded password detected"),
        ],
        logic_findings=[
            LogicFinding(severity="MEDIUM", type="null_dereference",
                        file="src/main/java/UserService.java", line=42,
                        description="Possible null dereference",
                        suggested_fix="Add null check before use"),
        ],
        generated_tests=[
            TestGenRow(output_path=str(cfg.output.java_tests_output / "UserServiceTest.java"),
                      source_file="UserService.java", methods_added=5,
                      coverage_before=72.0, coverage_after=88.5),
        ],
    )

    html_out, pdf_out = render_report(report_data, cfg, dry_run=False)
    print(f"HTML: {html_out}")
    print(f"PDF:  {pdf_out}")
    print("renderer.py smoke test passed.")
