"""pytest + FastAPI test generator for Python files."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from langchain_ollama import ChatOllama

if TYPE_CHECKING:
    from agent.config import AgentConfig
    from agent.reporting.models import RunStatus

LOG = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "python_test_gen.txt"
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n?|\n?```$", re.MULTILINE)


def detect_fastapi_structure(repo_path: Path) -> str:
    """Detect FastAPI project layout: 'routers', 'app_package', or 'flat'."""
    if (repo_path / "app" / "routers").exists():
        return "routers"
    if (repo_path / "app").is_dir() and (repo_path / "app" / "__init__.py").exists():
        return "app_package"
    return "flat"


def _existing_test_functions(test_file: Path) -> set[str]:
    """Parse an existing test file and return all top-level function names."""
    if not test_file.exists():
        return set()
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8", errors="replace"))
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
    except SyntaxError as exc:
        LOG.warning("Could not parse existing test file %s: %s", test_file, exc)
        return set()


def _strip_fences(code: str) -> str:
    return _FENCE_RE.sub("", code).strip()


def _call_llm(llm: ChatOllama, prompt: str, config: AgentConfig, label: str) -> str | None:
    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except requests.exceptions.ConnectionError:
        LOG.error("Ollama is not reachable at %s. Is it running?", config.llm.base_url)
        raise SystemExit(1)
    except requests.exceptions.Timeout:
        LOG.warning("Ollama request timed out for %s — skipping", label)
        return None
    except Exception as exc:
        LOG.error("LLM call failed for %s: %s", label, exc, exc_info=True)
        return None


def _write_conftest(output_dir: Path, repo_path: Path) -> None:
    """Write a conftest.py that adds the repo root to sys.path for test discovery."""
    conftest = output_dir / "conftest.py"
    if conftest.exists():
        return
    conftest.write_text(
        f'"""conftest.py — adds the FastAPI repo root to sys.path for test imports."""\n'
        f"import sys\n"
        f"from pathlib import Path\n\n"
        f'sys.path.insert(0, str(Path("{repo_path}").resolve()))\n',
        encoding="utf-8",
    )
    LOG.info("Wrote conftest.py to %s", output_dir)


def generate_python_tests(
    source_file: Path,
    uncovered_lines: list[int],
    config: AgentConfig,
    run_status: RunStatus,
    dry_run: bool = False,
) -> Path | None:
    """Generate a pytest test file for a Python source file.

    Returns the output Path if a file was written (or would be in dry-run), else None.
    """
    source = source_file.read_text(encoding="utf-8", errors="replace")
    repo_path = config.repos.python_repo_path
    structure = detect_fastapi_structure(repo_path)

    output_dir = config.output.python_tests_output
    test_filename = f"test_{source_file.stem}.py"
    output_file = output_dir / test_filename

    existing_funcs = _existing_test_functions(output_file)

    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{file_path}", str(source_file))
        .replace("{uncovered_lines}", str(sorted(uncovered_lines)))
        .replace("{existing_test_functions}", str(sorted(existing_funcs)))
        .replace("{fastapi_structure}", structure)
        .replace("{source_code}", source)
    )

    llm = ChatOllama(
        model=config.llm.model,
        base_url=config.llm.base_url,
        temperature=config.llm.temperature,
        timeout=config.llm.request_timeout,
    )

    raw = _call_llm(llm, prompt, config, f"python/{source_file.stem}")
    if raw is None:
        return None

    generated = _strip_fences(raw)

    if not generated.strip():
        msg = f"LLM returned empty output for {source_file.stem} — skipping"
        LOG.warning(msg)
        run_status.issues.append(msg)
        return None

    if dry_run:
        LOG.info("[dry-run] Would write %s", output_file)
        return output_file

    # Append-only: if file exists, extract new test functions and append
    if output_file.exists():
        generated = _merge_test_functions(output_file, generated, existing_funcs)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(generated, encoding="utf-8")
    _write_conftest(output_dir, repo_path)
    LOG.info("Wrote Python test file: %s", output_file)
    return output_file


def _merge_test_functions(
    existing_file: Path,
    new_code: str,
    existing_funcs: set[str],
) -> str:
    """Append new test functions from new_code to the existing test file."""
    existing_content = existing_file.read_text(encoding="utf-8", errors="replace")

    try:
        new_tree = ast.parse(new_code)
    except SyntaxError as exc:
        LOG.warning("New generated code has syntax errors: %s — overwriting file", exc)
        return new_code

    new_lines = new_code.splitlines()
    appended = 0

    additions: list[str] = []
    for node in new_tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if node.name in existing_funcs:
            LOG.debug("Skipping duplicate test function: %s", node.name)
            continue

        # Extract the function source lines (account for decorators)
        start = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
        end = node.end_lineno  # type: ignore[attr-defined]
        func_source = "\n".join(new_lines[start:end])
        additions.append(func_source)
        appended += 1

    if not additions:
        return existing_content

    merged = existing_content.rstrip() + "\n\n" + "\n\n".join(additions) + "\n"
    LOG.info("Appended %d new test functions to %s", appended, existing_file)
    return merged


if __name__ == "__main__":
    import sys
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from agent.config import get_config, validate_runtime
    from agent.reporting.models import RunStatus as _RunStatus

    cfg = get_config()
    validate_runtime(cfg)

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    sample = fixtures / "sample_router.py"
    if not sample.exists():
        print(f"Fixture not found: {sample}")
        sys.exit(1)

    rs = _RunStatus.empty(cfg.llm.model)
    out = generate_python_tests(
        source_file=sample,
        uncovered_lines=[26, 34, 42, 50],
        config=cfg,
        run_status=rs,
        dry_run=False,
    )
    if out:
        print(f"Generated: {out}")
        print(out.read_text()[:500])
    print("python_gen.py smoke test passed.")
