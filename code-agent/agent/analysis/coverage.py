"""Coverage report parsers for JaCoCo (Java) and pytest-cov/Cobertura (Python)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config import AgentConfig

LOG = logging.getLogger(__name__)


@dataclass
class FileCoverage:
    """Coverage data for a single class or source file."""
    name: str             # Class name (Java) or relative file path (Python)
    file_path: str        # Absolute path on disk
    covered_lines: int
    total_lines: int
    uncovered_line_numbers: list[int] = field(default_factory=list)

    @property
    def pct(self) -> float:
        if self.total_lines == 0:
            return 100.0
        return round(self.covered_lines / self.total_lines * 100, 2)


# ---------------------------------------------------------------------------
# JaCoCo XML parser
# ---------------------------------------------------------------------------

def parse_jacoco(config: AgentConfig) -> list[FileCoverage]:
    """Parse JaCoCo XML report. Returns per-class coverage data."""
    java_repo = config.repos.java_repo_path
    xml_path = java_repo / config.coverage.jacoco_report_path

    if not xml_path.exists():
        LOG.warning("JaCoCo report not found at %s. Run 'mvn jacoco:report' first.", xml_path)
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        LOG.error("Failed to parse JaCoCo XML at %s: %s", xml_path, exc)
        return []

    results: list[FileCoverage] = []

    for package in root.findall("package"):
        pkg_name = package.get("name", "")  # e.g. "com/example/service"

        # Build a line-hit map from <sourcefile> elements
        # <line nr="42" mi="0" ci="3" mb="0" cb="0"/>
        # mi=missed instructions, ci=covered instructions
        sourcefile_lines: dict[str, dict[int, bool]] = {}
        for sf in package.findall("sourcefile"):
            sf_name = sf.get("name", "")  # e.g. "UserService.java"
            line_covered: dict[int, bool] = {}
            for line_el in sf.findall("line"):
                nr_str = line_el.get("nr", "0")
                ci_str = line_el.get("ci", "0")
                nr = int(nr_str) if nr_str.isdigit() else 0
                ci = int(ci_str) if ci_str.isdigit() else 0
                line_covered[nr] = ci > 0
            sourcefile_lines[sf_name] = line_covered

        for cls in package.findall("class"):
            class_name = cls.get("name", "")  # e.g. "com/example/service/UserService"
            source_file_name = cls.get("sourcefilename", "")  # e.g. "UserService.java"

            # Class-level LINE counter
            line_counter = None
            for counter in cls.findall("counter"):
                if counter.get("type") == "LINE":
                    line_counter = counter
                    break

            if line_counter is None:
                continue

            missed = int(line_counter.get("missed", "0"))
            covered = int(line_counter.get("covered", "0"))
            total = missed + covered

            # Per-line uncovered numbers from the matching sourcefile
            uncovered: list[int] = []
            if source_file_name in sourcefile_lines:
                for line_nr, is_covered in sorted(sourcefile_lines[source_file_name].items()):
                    if not is_covered:
                        uncovered.append(line_nr)

            # Derive absolute file path
            java_source_root = java_repo / "src" / "main" / "java"
            abs_path = java_source_root / class_name.replace("/", "/")
            if source_file_name:
                abs_path = java_source_root / pkg_name / source_file_name

            results.append(
                FileCoverage(
                    name=class_name.replace("/", "."),
                    file_path=str(abs_path),
                    covered_lines=covered,
                    total_lines=total,
                    uncovered_line_numbers=uncovered,
                )
            )

    LOG.info("JaCoCo: parsed %d classes", len(results))
    return results


# ---------------------------------------------------------------------------
# pytest-cov / Cobertura XML parser
# ---------------------------------------------------------------------------

def parse_pytest_cov(config: AgentConfig) -> list[FileCoverage]:
    """Parse pytest-cov Cobertura XML. Returns per-file coverage data."""
    python_repo = config.repos.python_repo_path
    xml_path = python_repo / config.coverage.pytest_cov_xml

    if not xml_path.exists():
        LOG.warning(
            "pytest-cov XML report not found at %s. "
            "Run 'pytest --cov=. --cov-report=xml' first.",
            xml_path,
        )
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        LOG.error("Failed to parse coverage.xml at %s: %s", xml_path, exc)
        return []

    results: list[FileCoverage] = []

    for cls in root.iter("class"):
        filename = cls.get("filename", "")
        if not filename:
            continue

        abs_path = python_repo / filename if not Path(filename).is_absolute() else Path(filename)

        covered = 0
        total = 0
        uncovered: list[int] = []

        for line_el in cls.findall(".//line"):
            nr_str = line_el.get("number", "0")
            hits_str = line_el.get("hits", "0")
            nr = int(nr_str) if nr_str.isdigit() else 0
            hits = int(hits_str) if hits_str.isdigit() else 0
            total += 1
            if hits > 0:
                covered += 1
            else:
                uncovered.append(nr)

        results.append(
            FileCoverage(
                name=filename,
                file_path=str(abs_path),
                covered_lines=covered,
                total_lines=total,
                uncovered_line_numbers=uncovered,
            )
        )

    LOG.info("pytest-cov: parsed %d files", len(results))
    return results


def below_target(
    coverage_list: list[FileCoverage], target_pct: float
) -> list[FileCoverage]:
    """Filter to files/classes below the coverage target percentage."""
    return [c for c in coverage_list if c.pct < target_pct]


if __name__ == "__main__":
    import sys
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agent.config import get_config

    cfg = get_config()

    print("--- JaCoCo parse ---")
    java_cov = parse_jacoco(cfg)
    for c in java_cov[:5]:
        print(f"  {c.name}: {c.pct}% ({c.covered_lines}/{c.total_lines} lines)")
        if c.uncovered_line_numbers:
            print(f"    uncovered: {c.uncovered_line_numbers[:10]}")

    print("\n--- pytest-cov parse ---")
    py_cov = parse_pytest_cov(cfg)
    for c in py_cov[:5]:
        print(f"  {c.name}: {c.pct}% ({c.covered_lines}/{c.total_lines} lines)")
        if c.uncovered_line_numbers:
            print(f"    uncovered: {c.uncovered_line_numbers[:10]}")

    print("\ncoverage.py smoke test passed.")
