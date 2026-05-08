# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Contains

A single project: `code-agent/` — a fully local AI agent that analyzes Java Spring Boot and FastAPI Python codebases, auto-generates JUnit 5 / pytest unit tests, runs static analysis (SpotBugs, Bandit, Semgrep, OWASP Dependency-Check), and produces weekly HTML+PDF reports. All inference runs locally via Ollama; no external API calls.

See [code-agent/CLAUDE.md](code-agent/CLAUDE.md) for module-level guidance, commands, and architecture details.

## Environment

- **OS**: Windows 11 + WSL2 (Ubuntu). All agent code runs **inside WSL2**.
- **Ollama**: Runs on the **Windows host** (not inside WSL2). Access it via Windows host IP.
  - Find host IP from WSL2: `ip route show default | awk '{print $3}'`
- **LLM model**: `codellama:13b-q4` (no 24GB GPU available)
- **Output base**: `/home/neeraj/agent-output/`

## Quick Start

```bash
# Inside WSL2, from the code-agent/ directory:
bash scripts/setup.sh          # one-time setup
source venv/bin/activate
python3 agent/main.py --dry-run  # verify without writing anything
python3 agent/main.py            # full pipeline run
```

## Key Constraints

- All paths use `pathlib.Path` — no hardcoded strings
- Generated tests are written to `/home/neeraj/agent-output/generated-tests/` only — never into either repo
- `requirements.txt` uses pinned `==` versions throughout
- Every subprocess has an explicit `timeout=` kwarg
- All Ollama calls handle `ConnectionError` (exit 1) and `Timeout` (log + skip)
