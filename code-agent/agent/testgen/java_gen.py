"""JUnit 5 + Mockito test generator for Java classes."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from langchain_ollama import ChatOllama

if TYPE_CHECKING:
    from agent.config import AgentConfig
    from agent.ingestion.indexer import CodeIndexer
    from agent.reporting.models import RunStatus

LOG = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "java_test_gen.txt"
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n?|\n?```$", re.MULTILINE)
_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_CLASS_RE = re.compile(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)")
_TEST_METHOD_RE = re.compile(r"\bvoid\s+(\w+)\s*\(")


def _extract_package(source: str) -> str:
    m = _PACKAGE_RE.search(source)
    return m.group(1) if m else ""


def _extract_class_name(source: str) -> str:
    m = _CLASS_RE.search(source)
    return m.group(1) if m else ""


def _existing_test_methods(test_file: Path) -> set[str]:
    if not test_file.exists():
        return set()
    content = test_file.read_text(encoding="utf-8", errors="replace")
    return set(_TEST_METHOD_RE.findall(content))


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


def generate_java_tests(
    source_file: Path,
    uncovered_lines: list[int],
    config: AgentConfig,
    indexer: CodeIndexer,
    run_status: RunStatus,
    dry_run: bool = False,
) -> Path | None:
    """Generate a JUnit 5 test file for a Java source class.

    Returns the output Path if a file was written (or would be in dry-run), else None.
    """
    source = source_file.read_text(encoding="utf-8", errors="replace")
    package = _extract_package(source)
    class_name = _extract_class_name(source)

    if not class_name:
        msg = f"Could not determine class name from {source_file} — skipping"
        LOG.warning(msg)
        run_status.issues.append(msg)
        return None

    # Derive output path from package structure
    package_path = Path(*package.split(".")) if package else Path()
    output_dir = config.output.java_tests_output / package_path
    output_file = output_dir / f"{class_name}Test.java"

    existing_methods = _existing_test_methods(output_file)

    # Retrieve class chunks + dependency chunks from ChromaDB
    class_chunks = indexer.query("java", f"{class_name} {source_file}", top_k=5)
    dep_chunks = indexer.query("java", f"dependencies of {class_name}", top_k=5)
    dep_text = "\n\n".join(
        f"// {c.class_name}.{c.method_name}\n{c.content}"
        for c in dep_chunks
        if c.class_name != class_name
    )

    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{package}", package)
        .replace("{class_name}", class_name)
        .replace("{uncovered_lines}", str(sorted(uncovered_lines)))
        .replace("{existing_test_methods}", str(sorted(existing_methods)))
        .replace("{dependency_chunks}", dep_text or "(none)")
        .replace("{source_code}", source)
    )

    llm = ChatOllama(
        model=config.llm.model,
        base_url=config.llm.base_url,
        temperature=config.llm.temperature,
        timeout=config.llm.request_timeout,
    )

    raw = _call_llm(llm, prompt, config, f"java/{class_name}")
    if raw is None:
        return None

    generated = _strip_fences(raw)

    if not generated.strip().startswith("package") and not generated.strip().startswith("import"):
        msg = f"LLM output for {class_name} does not look like Java source — skipping"
        LOG.warning(msg)
        run_status.issues.append(msg)
        return None

    if dry_run:
        LOG.info("[dry-run] Would write %s", output_file)
        return output_file

    # Append-only: if file exists, extract new @Test methods and merge
    if output_file.exists():
        generated = _merge_test_methods(output_file, generated, existing_methods, class_name, package)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(generated, encoding="utf-8")
    LOG.info("Wrote Java test file: %s", output_file)
    return output_file


def _merge_test_methods(
    existing_file: Path,
    new_code: str,
    existing_methods: set[str],
    class_name: str,
    package: str,
) -> str:
    """Append new @Test methods from new_code into the existing test file."""
    existing_content = existing_file.read_text(encoding="utf-8", errors="replace")

    # Extract all @Test + method blocks from new_code
    # Pattern: @Test followed by optional annotations and then a void method
    test_block_re = re.compile(
        r"(@Test\b(?:[\s\S]*?)(?:public\s+)?void\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\{(?:[^{}]|\{[^{}]*\})*\})",
        re.MULTILINE,
    )

    new_methods_added = 0
    merged = existing_content.rstrip()

    # Find the closing brace of the test class
    last_brace_idx = merged.rfind("}")
    if last_brace_idx == -1:
        return new_code  # Can't parse existing file — overwrite

    for match in test_block_re.finditer(new_code):
        method_name = match.group(2)
        if method_name in existing_methods:
            LOG.debug("Skipping duplicate test method: %s", method_name)
            continue
        block = match.group(1).strip()
        merged = merged[:last_brace_idx].rstrip() + "\n\n    " + block + "\n" + merged[last_brace_idx:]
        last_brace_idx = merged.rfind("}")
        new_methods_added += 1

    LOG.info("Appended %d new test methods to %s", new_methods_added, existing_file)
    return merged


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

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    indexer = CodeIndexer(cfg)
    indexer.index_repo(fixtures, "java", dry_run=False)

    rs = _RunStatus.empty(cfg.llm.model)
    sample = fixtures / "SampleService.java"
    if not sample.exists():
        print(f"Fixture not found: {sample}")
        sys.exit(1)

    out = generate_java_tests(
        source_file=sample,
        uncovered_lines=[22, 23, 30, 31, 40],
        config=cfg,
        indexer=indexer,
        run_status=rs,
        dry_run=False,
    )
    if out:
        print(f"Generated: {out}")
        print(out.read_text()[:500])
    print("java_gen.py smoke test passed.")
