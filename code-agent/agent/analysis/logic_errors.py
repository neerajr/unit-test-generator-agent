"""LLM-based logic error analysis via RAG retrieval from ChromaDB."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

import requests
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from agent.ingestion.indexer import CodeIndexer

if TYPE_CHECKING:
    from agent.config import AgentConfig
    from agent.reporting.models import RunStatus

LOG = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "logic_analysis.txt"


class LogicFinding(BaseModel):
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    type: Literal[
        "null_dereference",
        "exception_handling",
        "transaction_boundary",
        "race_condition",
        "incorrect_assumption",
        "other",
    ]
    file: str
    line: Optional[int] = None
    description: str
    suggested_fix: str


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_chunks_for_prompt(chunks) -> str:
    parts: list[str] = []
    for c in chunks:
        parts.append(
            f"--- File: {c.file_path} | Class: {c.class_name} | Method: {c.method_name} "
            f"| Lines: {c.start_line}-{c.end_line} ---\n{c.content}"
        )
    return "\n\n".join(parts)


def _call_llm(
    llm: ChatOllama,
    prompt: str,
    config: AgentConfig,
    run_status: RunStatus,
    context_label: str,
) -> str | None:
    """Call LLM and return raw string response, or None on unrecoverable error."""
    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except requests.exceptions.ConnectionError:
        LOG.error(
            "Ollama is not reachable at %s. Is it running?",
            config.llm.base_url,
        )
        raise SystemExit(1)
    except requests.exceptions.Timeout:
        msg = f"Ollama request timed out for {context_label}"
        LOG.warning(msg)
        run_status.issues.append(msg)
        return None
    except Exception as exc:
        msg = f"LLM call failed for {context_label}: {exc}"
        LOG.error(msg, exc_info=True)
        run_status.issues.append(msg)
        return None


def _parse_llm_json(
    raw: str,
    llm: ChatOllama,
    config: AgentConfig,
    run_status: RunStatus,
    context_label: str,
    log_path: Path,
) -> list[dict] | None:
    """Parse JSON from LLM output with one retry on failure."""
    # Strip markdown fences if the model wrapped the output anyway
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        LOG.warning("LLM returned non-array JSON for %s", context_label)
        return []
    except json.JSONDecodeError:
        pass

    # First parse failed — retry with correction instruction
    correction = (
        "Your previous response was not valid JSON. "
        "Return only the raw JSON array, nothing else. "
        "Do not include any markdown fences, explanations, or text outside the array.\n\n"
        + raw
    )
    retry_raw = _call_llm(llm, correction, config, run_status, f"{context_label} (retry)")
    if retry_raw is None:
        return None

    retry_cleaned = retry_raw.strip()
    if retry_cleaned.startswith("```"):
        lines = retry_cleaned.splitlines()
        retry_cleaned = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(retry_cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Both attempts failed — log raw response and skip
    msg = f"LLM returned unparseable JSON for {context_label} (both attempts). Logged to {log_path}"
    LOG.error(msg)
    run_status.issues.append(msg)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {context_label} ===\n{raw}\n---RETRY---\n{retry_raw}\n")
    return None


def _coerce_finding(raw: dict) -> LogicFinding | None:
    """Coerce a raw dict from LLM JSON into a LogicFinding, discarding invalid entries."""
    _VALID_SEVERITY = {"HIGH", "MEDIUM", "LOW"}
    _VALID_TYPE = {
        "null_dereference",
        "exception_handling",
        "transaction_boundary",
        "race_condition",
        "incorrect_assumption",
        "other",
    }
    severity = str(raw.get("severity", "LOW")).upper()
    if severity not in _VALID_SEVERITY:
        severity = "LOW"
    type_ = str(raw.get("type", "other")).lower()
    if type_ not in _VALID_TYPE:
        type_ = "other"
    line_raw = raw.get("line")
    line: int | None = int(line_raw) if line_raw and str(line_raw).isdigit() else None
    try:
        return LogicFinding(
            severity=severity,  # type: ignore[arg-type]
            type=type_,  # type: ignore[arg-type]
            file=str(raw.get("file", "")),
            line=line,
            description=str(raw.get("description", "")),
            suggested_fix=str(raw.get("suggested_fix", "")),
        )
    except Exception as exc:
        LOG.debug("Skipping malformed finding dict: %s — %s", raw, exc)
        return None


def analyze_repo(
    config: AgentConfig,
    indexer: CodeIndexer,
    language: str,
    run_status: RunStatus,
) -> list[LogicFinding]:
    """Analyze all classes in a language's ChromaDB collection for logic errors."""
    collection = indexer._java_col if language == "java" else indexer._python_col

    # Enumerate unique (class_name, file_path) pairs from the collection
    all_meta = collection.get(include=["metadatas"])
    if not all_meta or not all_meta.get("metadatas"):
        LOG.info("No indexed chunks found for %s — skipping logic analysis", language)
        return []

    seen: set[tuple[str, str]] = set()
    classes: list[tuple[str, str]] = []
    for meta in all_meta["metadatas"]:
        key = (meta.get("class_name", ""), meta.get("file_path", ""))
        if key not in seen and key[0] != "fallback":
            seen.add(key)
            classes.append(key)

    LOG.info("Logic analysis: %d unique classes in %s repo", len(classes), language)

    prompt_template = _load_prompt_template()
    llm = ChatOllama(
        model=config.llm.model,
        base_url=config.llm.base_url,
        temperature=config.llm.temperature,
        timeout=config.llm.request_timeout,
    )
    log_path = config.output.reports_dir / "llm-errors.log"
    all_findings: list[LogicFinding] = []

    for class_name, file_path in classes:
        query = f"{class_name} {file_path}"
        chunks = indexer.query(language, query, top_k=config.rag.top_k)

        if not chunks:
            continue

        code_text = _format_chunks_for_prompt(chunks)
        prompt = prompt_template.replace("{code_chunks}", code_text)

        context_label = f"{language}/{class_name}"
        raw = _call_llm(llm, prompt, config, run_status, context_label)
        if raw is None:
            continue

        parsed = _parse_llm_json(raw, llm, config, run_status, context_label, log_path)
        if parsed is None:
            continue

        for item in parsed:
            finding = _coerce_finding(item)
            if finding:
                all_findings.append(finding)

    LOG.info(
        "Logic analysis complete for %s: %d findings across %d classes",
        language,
        len(all_findings),
        len(classes),
    )
    return all_findings


if __name__ == "__main__":
    import sys
    import logging as _logging
    from pathlib import Path

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agent.config import get_config, validate_runtime
    from agent.ingestion.indexer import CodeIndexer as _Indexer
    from agent.reporting.models import RunStatus as _RunStatus

    cfg = get_config()
    validate_runtime(cfg)

    rs = _RunStatus.empty(cfg.llm.model)
    indexer = _Indexer(cfg)

    # Index fixtures first
    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    indexer.index_repo(fixtures, "python", dry_run=False)

    findings = analyze_repo(cfg, indexer, "python", rs)
    print(f"Logic findings: {len(findings)}")
    for f in findings[:3]:
        print(f"  [{f.severity}] {f.type}: {f.file}:{f.line} — {f.description[:80]}")
    print("logic_errors.py smoke test passed.")
