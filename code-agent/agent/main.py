"""Orchestrator — full pipeline entry point for the code analysis agent."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Reduce noise from third-party libraries
    for noisy in ("httpx", "chromadb", "httpcore", "urllib3", "weasyprint"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="code-agent",
        description="Local AI agent for code analysis and unit test generation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run the full pipeline without writing any test files, reports, or "
            "ChromaDB upserts. Useful for first-time verification."
        ),
    )
    parser.add_argument(
        "--repo",
        choices=["java", "python"],
        default=None,
        help="Limit the run to a single repo language (default: both).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: config/config.yaml relative to project root).",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip re-indexing into ChromaDB (use existing index).",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip vulnerability and logic analysis (run test generation only).",
    )
    return parser.parse_args()


def run_pipeline(
    dry_run: bool = False,
    repo_filter: str | None = None,
    config_path: Path | None = None,
    skip_ingest: bool = False,
    skip_analysis: bool = False,
) -> int:
    """Execute the full agent pipeline. Returns exit code (0 = success)."""
    _setup_logging()

    # --- Step 1: Load config and validate environment ---
    from agent.config import get_config, load_config, validate_runtime

    try:
        cfg = load_config(config_path) if config_path else get_config()
    except FileNotFoundError as exc:
        LOG.error("Cannot load config: %s", exc)
        return 1

    validate_runtime(cfg)  # exits with code 1 on failure

    from agent.reporting.models import RunStatus

    run_status = RunStatus.empty(cfg.llm.model)
    start_time = time.monotonic()

    LOG.info("=" * 60)
    LOG.info("code-agent starting  |  model=%s  |  dry_run=%s", cfg.llm.model, dry_run)
    LOG.info("=" * 60)

    run_languages = (
        [repo_filter] if repo_filter else ["java", "python"]
    )

    # --- Step 2: Ingestion (chunk + embed + index) ---
    if not skip_ingest:
        from agent.ingestion.indexer import CodeIndexer

        try:
            indexer = CodeIndexer(cfg)
        except RuntimeError as exc:
            LOG.error("ChromaDB initialization failed: %s", exc)
            return 1

        for lang in run_languages:
            repo_path = (
                cfg.repos.java_repo_path
                if lang == "java"
                else cfg.repos.python_repo_path
            )
            LOG.info("Indexing %s repo: %s", lang, repo_path)
            try:
                count = indexer.index_repo(repo_path, lang, dry_run=dry_run)
                LOG.info("Indexed %d chunks for %s", count, lang)
                run_status.files_scanned += count
            except Exception as exc:
                msg = f"Ingestion failed for {lang}: {exc}"
                LOG.error(msg, exc_info=True)
                run_status.add_issue(msg)
    else:
        LOG.info("Skipping ingestion (--skip-ingest)")
        from agent.ingestion.indexer import CodeIndexer

        try:
            indexer = CodeIndexer(cfg)
        except RuntimeError as exc:
            LOG.error("ChromaDB initialization failed: %s", exc)
            return 1

    # --- Step 3: Static analysis and vulnerability scanning ---
    from agent.analysis.vulnerability import VulnFinding

    vuln_findings: list[VulnFinding] = []
    if not skip_analysis:
        LOG.info("Running vulnerability scans...")
        from agent.analysis.vulnerability import run_all as run_vuln

        try:
            vuln_findings = run_vuln(cfg, run_status)
        except Exception as exc:
            msg = f"Vulnerability scan failed unexpectedly: {exc}"
            LOG.error(msg, exc_info=True)
            run_status.add_issue(msg)

    # --- Step 4: Logic error analysis (LLM-based) ---
    from agent.analysis.logic_errors import LogicFinding

    logic_findings: list[LogicFinding] = []
    if not skip_analysis:
        LOG.info("Running logic error analysis...")
        from agent.analysis.logic_errors import analyze_repo

        for lang in run_languages:
            try:
                findings = analyze_repo(cfg, indexer, lang, run_status)
                logic_findings.extend(findings)
            except SystemExit:
                raise  # Ollama unreachable — propagate
            except Exception as exc:
                msg = f"Logic analysis failed for {lang}: {exc}"
                LOG.error(msg, exc_info=True)
                run_status.add_issue(msg)

    # --- Step 5: Coverage measurement (before test generation) ---
    from agent.analysis.coverage import parse_jacoco, parse_pytest_cov
    from agent.reporting.models import CoverageRow

    initial_java_coverage = parse_jacoco(cfg) if "java" in run_languages else []
    initial_python_coverage = parse_pytest_cov(cfg) if "python" in run_languages else []

    def _to_coverage_rows(
        before: list, after: list, target: float
    ) -> list[CoverageRow]:
        before_map = {c.name: c.pct for c in before}
        rows: list[CoverageRow] = []
        for fc in after:
            prev = before_map.get(fc.name, fc.pct)
            rows.append(
                CoverageRow(
                    name=fc.name,
                    prev_pct=prev,
                    curr_pct=fc.pct,
                    delta=round(fc.pct - prev, 2),
                    met=fc.pct >= target,
                )
            )
        return rows

    # --- Step 6: Test generation with iterative coverage loops ---
    from agent.testgen.coverage_loop import (
        LoopResult,
        run_java_coverage_loop,
        run_python_coverage_loop,
    )
    from agent.reporting.models import TestGenRow

    java_loop_result: LoopResult | None = None
    python_loop_result: LoopResult | None = None

    if "java" in run_languages:
        LOG.info("Running Java coverage improvement loop...")
        try:
            java_loop_result = run_java_coverage_loop(cfg, indexer, run_status, dry_run=dry_run)
        except SystemExit:
            raise
        except Exception as exc:
            msg = f"Java coverage loop failed: {exc}"
            LOG.error(msg, exc_info=True)
            run_status.add_issue(msg)

    if "python" in run_languages:
        LOG.info("Running Python coverage improvement loop...")
        try:
            python_loop_result = run_python_coverage_loop(cfg, run_status, dry_run=dry_run)
        except SystemExit:
            raise
        except Exception as exc:
            msg = f"Python coverage loop failed: {exc}"
            LOG.error(msg, exc_info=True)
            run_status.add_issue(msg)

    # --- Step 7: Final coverage snapshot (after test generation) ---
    final_java_coverage = parse_jacoco(cfg) if "java" in run_languages else []
    final_python_coverage = parse_pytest_cov(cfg) if "python" in run_languages else []

    java_coverage_rows = _to_coverage_rows(
        initial_java_coverage, final_java_coverage, cfg.coverage.target_pct
    )
    python_coverage_rows = _to_coverage_rows(
        initial_python_coverage, final_python_coverage, cfg.coverage.target_pct
    )

    # Build TestGenRow list from loop results
    generated_test_rows: list[TestGenRow] = []
    for loop_result in filter(None, [java_loop_result, python_loop_result]):
        for gen_path in loop_result.generated_test_files:
            src_name = gen_path.stem.replace("Test", "").replace("test_", "")
            cov_before = loop_result.initial_coverage.get(src_name, 0.0)
            cov_after = loop_result.final_coverage.get(src_name, cov_before)
            generated_test_rows.append(
                TestGenRow(
                    output_path=str(gen_path),
                    source_file=src_name,
                    methods_added=0,  # exact count would require parsing generated files
                    coverage_before=cov_before,
                    coverage_after=cov_after,
                )
            )

    # --- Step 8: Finalise RunStatus ---
    run_status.duration_seconds = round(time.monotonic() - start_time, 1)

    # --- Step 9: Render report ---
    from agent.reporting.models import ReportData
    from agent.reporting.renderer import render_report

    report_data = ReportData(
        status=run_status,
        java_coverage=java_coverage_rows,
        python_coverage=python_coverage_rows,
        vuln_findings=vuln_findings,
        logic_findings=logic_findings,
        generated_tests=generated_test_rows,
    )

    try:
        html_path, pdf_path = render_report(report_data, cfg, dry_run=dry_run)
        LOG.info("Report written: %s", html_path)
        LOG.info("Report written: %s", pdf_path)
    except Exception as exc:
        msg = f"Report rendering failed: {exc}"
        LOG.error(msg, exc_info=True)
        run_status.add_issue(msg)

    # --- Done ---
    LOG.info("=" * 60)
    LOG.info(
        "code-agent complete  |  duration=%.1fs  |  issues=%d",
        run_status.duration_seconds,
        len(run_status.issues),
    )
    if run_status.issues:
        LOG.warning("Run issues:")
        for issue in run_status.issues:
            LOG.warning("  - %s", issue)
    LOG.info("=" * 60)

    return 0


def main() -> None:
    args = _parse_args()
    code = run_pipeline(
        dry_run=args.dry_run,
        repo_filter=args.repo,
        config_path=args.config,
        skip_ingest=args.skip_ingest,
        skip_analysis=args.skip_analysis,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
