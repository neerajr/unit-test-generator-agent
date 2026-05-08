"""Iterative coverage improvement loop for both Java (JaCoCo) and Python (pytest-cov)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from agent.analysis.coverage import FileCoverage, below_target, parse_jacoco, parse_pytest_cov
from agent.testgen.java_gen import generate_java_tests
from agent.testgen.python_gen import generate_python_tests

if TYPE_CHECKING:
    from agent.config import AgentConfig
    from agent.ingestion.indexer import CodeIndexer
    from agent.reporting.models import RunStatus

LOG = logging.getLogger(__name__)


@dataclass
class LoopResult:
    language: str
    iterations_run: int
    initial_coverage: dict[str, float] = field(default_factory=dict)  # name → pct
    final_coverage: dict[str, float] = field(default_factory=dict)
    files_improved: list[str] = field(default_factory=list)
    generated_test_files: list[Path] = field(default_factory=list)


def _run_subprocess(cmd: list[str], cwd: Path, timeout: int, label: str) -> bool:
    """Run subprocess, log stderr on failure. Returns True on success."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
        )
        if result.returncode != 0:
            LOG.warning("%s exited with code %d", label, result.returncode)
            if result.stderr:
                LOG.warning("%s stderr:\n%s", label, result.stderr[:3000])
            return False
        return True
    except subprocess.TimeoutExpired:
        LOG.error("%s timed out after %ds", label, timeout)
        return False
    except Exception as exc:
        LOG.error("%s failed: %s", label, exc, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Java loop
# ---------------------------------------------------------------------------

def run_java_coverage_loop(
    config: AgentConfig,
    indexer: CodeIndexer,
    run_status: RunStatus,
    dry_run: bool = False,
) -> LoopResult:
    java_repo = config.repos.java_repo_path
    pom_path = java_repo / "pom.xml"
    java_tests_output = config.output.java_tests_output
    target_pct = config.coverage.target_pct
    max_iterations = config.coverage.max_iterations

    if not pom_path.exists():
        msg = f"pom.xml not found at {pom_path} — skipping Java coverage loop"
        LOG.warning(msg)
        run_status.issues.append(msg)
        return LoopResult(language="java", iterations_run=0)

    result = LoopResult(language="java", iterations_run=0)

    for iteration in range(max_iterations):
        LOG.info("Java coverage loop — iteration %d/%d", iteration + 1, max_iterations)

        # Run Maven test + JaCoCo report
        # Pass -Dagent.tests.dir so build-helper-maven-plugin can include generated tests
        ok = _run_subprocess(
            [
                "mvn", "test", "jacoco:report",
                "-f", str(pom_path),
                "-q",
                f"-Dagent.tests.dir={java_tests_output}",
            ],
            cwd=java_repo,
            timeout=600,
            label=f"mvn test jacoco:report (iteration {iteration + 1})",
        )
        if not ok:
            msg = f"mvn test failed on Java coverage loop iteration {iteration + 1}"
            run_status.issues.append(msg)
            break

        # Parse JaCoCo
        coverage_list = parse_jacoco(config)
        if not coverage_list:
            LOG.warning("JaCoCo returned no data — stopping loop")
            break

        # Record initial coverage on first iteration
        if iteration == 0:
            result.initial_coverage = {c.name: c.pct for c in coverage_list}

        under_target = below_target(coverage_list, target_pct)
        LOG.info(
            "Java iteration %d: %d/%d classes below %.0f%% coverage",
            iteration + 1,
            len(under_target),
            len(coverage_list),
            target_pct,
        )

        if not under_target:
            LOG.info("All Java classes meet target coverage — stopping loop early")
            break

        # Generate tests for classes below target
        for fc in under_target:
            source_file = Path(fc.file_path)
            if not source_file.exists():
                LOG.debug("Source file not found, skipping: %s", source_file)
                continue

            generated = generate_java_tests(
                source_file=source_file,
                uncovered_lines=fc.uncovered_line_numbers,
                config=config,
                indexer=indexer,
                run_status=run_status,
                dry_run=dry_run,
            )
            if generated and generated not in result.generated_test_files:
                result.generated_test_files.append(generated)

        result.iterations_run = iteration + 1

    # Final coverage snapshot
    final_list = parse_jacoco(config)
    result.final_coverage = {c.name: c.pct for c in final_list}
    result.files_improved = [
        name
        for name, init_pct in result.initial_coverage.items()
        if result.final_coverage.get(name, init_pct) > init_pct
    ]

    LOG.info(
        "Java coverage loop complete: %d iterations, %d files improved, %d test files generated",
        result.iterations_run,
        len(result.files_improved),
        len(result.generated_test_files),
    )
    return result


# ---------------------------------------------------------------------------
# Python loop
# ---------------------------------------------------------------------------

def run_python_coverage_loop(
    config: AgentConfig,
    run_status: RunStatus,
    dry_run: bool = False,
) -> LoopResult:
    python_repo = config.repos.python_repo_path
    python_tests_output = config.output.python_tests_output
    coverage_xml = python_repo / config.coverage.pytest_cov_xml
    target_pct = config.coverage.target_pct
    max_iterations = config.coverage.max_iterations

    result = LoopResult(language="python", iterations_run=0)

    # Build the test collection directories for pytest
    test_dirs: list[str] = []
    repo_tests = python_repo / "tests"
    if repo_tests.exists():
        test_dirs.append(str(repo_tests))
    test_dirs.append(str(python_tests_output))

    for iteration in range(max_iterations):
        LOG.info("Python coverage loop — iteration %d/%d", iteration + 1, max_iterations)

        # Ensure output dir exists so pytest doesn't error if it's empty
        python_tests_output.mkdir(parents=True, exist_ok=True)

        # Build pytest command
        pytest_cmd = [
            "pytest",
            *test_dirs,
            f"--cov={python_repo}",
            f"--cov-report=xml:{coverage_xml}",
            "--cov-append",  # accumulate across test dirs
            "-q",
            "--tb=no",       # suppress tracebacks for faster runs
        ]

        ok = _run_subprocess(
            pytest_cmd,
            cwd=python_repo,
            timeout=300,
            label=f"pytest coverage (iteration {iteration + 1})",
        )
        if not ok:
            msg = f"pytest failed on Python coverage loop iteration {iteration + 1}"
            run_status.issues.append(msg)
            break

        # Parse coverage
        coverage_list = parse_pytest_cov(config)
        if not coverage_list:
            LOG.warning("pytest-cov returned no data — stopping loop")
            break

        if iteration == 0:
            result.initial_coverage = {c.name: c.pct for c in coverage_list}

        under_target = below_target(coverage_list, target_pct)
        LOG.info(
            "Python iteration %d: %d/%d files below %.0f%% coverage",
            iteration + 1,
            len(under_target),
            len(coverage_list),
            target_pct,
        )

        if not under_target:
            LOG.info("All Python files meet target coverage — stopping loop early")
            break

        for fc in under_target:
            source_file = Path(fc.file_path)
            if not source_file.exists():
                LOG.debug("Source file not found, skipping: %s", source_file)
                continue
            # Skip test files themselves
            if source_file.name.startswith("test_") or source_file.stem.endswith("_test"):
                continue

            generated = generate_python_tests(
                source_file=source_file,
                uncovered_lines=fc.uncovered_line_numbers,
                config=config,
                run_status=run_status,
                dry_run=dry_run,
            )
            if generated and generated not in result.generated_test_files:
                result.generated_test_files.append(generated)

        result.iterations_run = iteration + 1

    # Final coverage snapshot
    final_list = parse_pytest_cov(config)
    result.final_coverage = {c.name: c.pct for c in final_list}
    result.files_improved = [
        name
        for name, init_pct in result.initial_coverage.items()
        if result.final_coverage.get(name, init_pct) > init_pct
    ]

    LOG.info(
        "Python coverage loop complete: %d iterations, %d files improved, %d test files generated",
        result.iterations_run,
        len(result.files_improved),
        len(result.generated_test_files),
    )
    return result


if __name__ == "__main__":
    import sys
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from agent.config import get_config, validate_runtime
    from agent.ingestion.indexer import CodeIndexer
    from agent.reporting.models import RunStatus as _RunStatus

    cfg = get_config()
    validate_runtime(cfg)

    rs = _RunStatus.empty(cfg.llm.model)
    indexer = CodeIndexer(cfg)

    print("Running Java coverage loop (dry-run)...")
    java_result = run_java_coverage_loop(cfg, indexer, rs, dry_run=True)
    print(f"  Iterations: {java_result.iterations_run}")
    print(f"  Test files would be generated: {len(java_result.generated_test_files)}")

    print("\nRunning Python coverage loop (dry-run)...")
    py_result = run_python_coverage_loop(cfg, rs, dry_run=True)
    print(f"  Iterations: {py_result.iterations_run}")
    print(f"  Test files would be generated: {len(py_result.generated_test_files)}")

    print("\ncoverage_loop.py smoke test passed.")
