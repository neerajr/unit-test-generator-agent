# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A fully local AI agent (`code-agent`) that analyzes Java Spring Boot and FastAPI Python codebases, generates JUnit 5 / pytest unit tests, runs static analysis, and produces weekly HTML+PDF reports — all using Ollama locally (zero external API calls). Runs on Linux, macOS, WSL2, and Windows native.

## Commands

```bash
# First-time setup (run inside WSL2)
bash scripts/setup.sh

# Activate virtualenv (always do this before running)
source venv/bin/activate

# Dry-run (no writes — use for first-time verification)
python3 agent/main.py --dry-run

# Full pipeline run
python3 agent/main.py

# Single-repo run
python3 agent/main.py --repo java
python3 agent/main.py --repo python

# Per-module smoke tests
python3 agent/config.py
python3 agent/ingestion/chunker.py
python3 agent/ingestion/indexer.py
python3 agent/analysis/vulnerability.py
python3 agent/analysis/logic_errors.py
python3 agent/analysis/coverage.py
python3 agent/testgen/java_gen.py
python3 agent/testgen/python_gen.py
python3 agent/reporting/renderer.py
```

## Architecture

```
agent/
├── config.py          # Pydantic v2 config loader from config/config.yaml
├── main.py            # Pipeline orchestrator (ingest → analyze → testgen → report)
├── ingestion/
│   ├── chunker.py     # tree-sitter AST chunker (Java methods, Python functions + FastAPI decorators)
│   ├── embedder.py    # OllamaEmbeddings (nomic-embed-text), 32-chunk batches
│   └── indexer.py     # ChromaDB PersistentClient, git-diff delta re-indexing
├── analysis/
│   ├── vulnerability.py  # SpotBugs, OWASP DC, Bandit, Semgrep subprocess runners
│   ├── logic_errors.py   # LLM RAG analysis → LogicFinding Pydantic model
│   └── coverage.py       # JaCoCo XML + pytest-cov Cobertura XML parsers
├── testgen/
│   ├── java_gen.py    # JUnit 5 + Mockito generator, append-only output
│   ├── python_gen.py  # pytest + FastAPI TestClient generator, append-only output
│   └── coverage_loop.py  # Iterative coverage improvement, max 3 iterations
└── reporting/
    ├── models.py      # RunStatus, CoverageRow, TestGenRow, ReportData
    ├── renderer.py    # Jinja2 HTML → WeasyPrint PDF, run_history.json
    └── templates/     # report.html.j2, summary.html.j2
```

## Critical Environment Details

- **Paths**: Use `~` (home dir) or absolute paths. `~` is expanded at runtime on all platforms.
- **Ollama**: `base_url: "auto"` in config.yaml auto-detects the host:
  - WSL2 → Windows host IP (from `ip route show default`)
  - Linux / macOS / Windows native → `localhost`
  - Override: set `AGENT_OLLAMA_HOST=<ip>` env var or edit `environment.ollama_host` in config.yaml
- **Model**: Selected automatically by `setup.sh`/`setup.ps1` based on detected GPU VRAM.
  - GPU ≥ 24 GB → `qwen2.5-coder:32b` | GPU ≥ 8 GB → `codellama:13b-q4` | CPU → `codellama:7b-q4`
- **Output base**: `~/agent-output/` by default; change via `output.base_dir` in config.yaml
- **Generated tests**: written to `output.base_dir` ONLY — never into `src/test/` or `tests/`
- **Existing tests**: both repos have tests that must not be overwritten

## Key Constraints

- No placeholder `pass` or `# TODO` in any method body
- All file writes use `pathlib.Path` — no string concatenation for paths
- Every subprocess call has explicit `timeout=` and `try/except` with logged stderr
- Every Ollama call catches `ConnectionError` (→ `sys.exit(1)`) and `Timeout` (→ log + skip)
- `requirements.txt` uses pinned `==` versions only
- Every module has a `if __name__ == "__main__":` smoke-test block
