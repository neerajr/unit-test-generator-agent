"""Configuration loader — reads config/config.yaml into validated Pydantic models."""

from __future__ import annotations

import logging
import os
import platform as _platform_mod
import socket
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
import yaml
from pydantic import BaseModel, field_validator, model_validator

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable → config key mapping
# Any AGENT_* env var overrides the corresponding nested yaml key at load time.
# ---------------------------------------------------------------------------
_ENV_OVERRIDE_MAP: dict[str, tuple[str, ...]] = {
    "AGENT_LLM_BASE_URL":    ("llm", "base_url"),
    "AGENT_LLM_MODEL":       ("llm", "model"),
    "AGENT_LLM_EMBED_MODEL": ("llm", "embed_model"),
    "AGENT_LLM_TEMPERATURE": ("llm", "temperature"),
    "AGENT_LLM_TIMEOUT":     ("llm", "request_timeout"),
    "AGENT_OUTPUT_BASE":     ("output", "base_dir"),
    "AGENT_JAVA_REPO":       ("repos", "java_repo_path"),
    "AGENT_PYTHON_REPO":     ("repos", "python_repo_path"),
    "AGENT_OLLAMA_HOST":     ("environment", "ollama_host"),
    "AGENT_OLLAMA_PORT":     ("environment", "ollama_port"),
    "AGENT_PLATFORM":        ("system", "platform"),
    "AGENT_GPU_ENABLED":     ("system", "gpu_enabled"),
    "AGENT_GPU_VRAM_GB":     ("system", "gpu_vram_gb"),
    "AGENT_CHROMA_PATH":     ("rag", "chroma_path"),
    "AGENT_PYTHON_BIN":      ("environment", "python_bin"),
    "AGENT_JAVA_BIN":        ("environment", "java_bin"),
    "AGENT_MVN_BIN":         ("environment", "mvn_bin"),
    "HTTP_PROXY":            ("proxy", "http_proxy"),
    "HTTPS_PROXY":           ("proxy", "https_proxy"),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _resolve_path(raw: str) -> Path:
    """Expand ~ and ${VAR}/%VAR% environment variables, return absolute Path."""
    expanded = os.path.expandvars(raw)
    expanded = os.path.expanduser(expanded)
    return Path(expanded)


def _auto_detect_platform() -> str:
    """
    Detect execution environment.
    Returns one of: linux, macos, windows_wsl2, windows_native
    """
    system = _platform_mod.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows_native"
    if system == "linux":
        try:
            version = Path("/proc/version").read_text(encoding="utf-8", errors="replace").lower()
            if "microsoft" in version or "wsl" in version:
                return "windows_wsl2"
        except OSError:
            pass
        return "linux"
    return "linux"


def _auto_detect_ollama_host() -> str:
    """
    Detect the correct Ollama host address.
    WSL2: derives the Windows host IP from the default route gateway.
    All other platforms: returns localhost.
    Falls back to localhost on any error.
    """
    detected = _auto_detect_platform()
    if detected != "windows_wsl2":
        return "localhost"

    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.split()
            if "via" in parts:
                ip = parts[parts.index("via") + 1]
                socket.inet_aton(ip)  # validates it's a real IPv4 address
                LOG.info("WSL2 Windows host IP auto-detected: %s", ip)
                return ip
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, socket.error) as exc:
        LOG.warning("WSL2 host IP detection failed (%s) — falling back to localhost", exc)

    return "localhost"


def _apply_env_overrides(raw: dict) -> dict:
    """
    Apply AGENT_* environment variable overrides onto the raw YAML dict.
    Called before Pydantic model construction so env vars win over file values.
    """
    for env_var, key_path in _ENV_OVERRIDE_MAP.items():
        val = os.environ.get(env_var)
        if val is None:
            continue
        node = raw
        for key in key_path[:-1]:
            node = node.setdefault(key, {})
        node[key_path[-1]] = val
        LOG.debug("Config override: %s → %s = %r", env_var, ".".join(key_path), val)
    return raw


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SystemConfig(BaseModel):
    """Platform and GPU detection. All fields default to 'auto' (detected at load time)."""
    platform: str = "auto"      # auto | linux | macos | windows_wsl2 | windows_native
    gpu_enabled: str = "auto"   # auto | true | false
    gpu_vram_gb: str = "auto"   # auto | <integer as string>

    @field_validator("platform", mode="before")
    @classmethod
    def resolve_platform(cls, v: str) -> str:
        return _auto_detect_platform() if str(v) == "auto" else str(v)

    @field_validator("gpu_enabled", "gpu_vram_gb", mode="before")
    @classmethod
    def coerce_str(cls, v) -> str:
        return str(v)


class EnvironmentConfig(BaseModel):
    """Tool locations and Ollama connectivity. 'auto' means resolved at load time."""
    ollama_host: str = "auto"   # auto | localhost | <ip or hostname>
    ollama_port: int = 11434
    python_bin: str = "auto"    # auto | /path/to/python3
    java_bin: str = "auto"      # auto | /path/to/java
    mvn_bin: str = "auto"       # auto | /path/to/mvn

    @field_validator("ollama_host", mode="before")
    @classmethod
    def resolve_ollama_host(cls, v: str) -> str:
        return _auto_detect_ollama_host() if str(v) == "auto" else str(v)


class ReposConfig(BaseModel):
    java_repo_path: Path
    python_repo_path: Path

    @field_validator("java_repo_path", "python_repo_path", mode="before")
    @classmethod
    def expand_repo_paths(cls, v) -> Path:
        return _resolve_path(str(v))


class OutputConfig(BaseModel):
    base_dir: Path = Path("~/agent-output")
    java_tests_output: Optional[Path] = None
    python_tests_output: Optional[Path] = None
    reports_dir: Optional[Path] = None
    retain_weeks: int = 12

    @field_validator("base_dir", mode="before")
    @classmethod
    def expand_base(cls, v) -> Path:
        return _resolve_path(str(v))

    @field_validator("java_tests_output", "python_tests_output", "reports_dir", mode="before")
    @classmethod
    def expand_optional_paths(cls, v) -> Optional[Path]:
        if v is None:
            return None
        return _resolve_path(str(v))

    @model_validator(mode="after")
    def derive_subdirs(self) -> "OutputConfig":
        base = self.base_dir
        if self.java_tests_output is None:
            self.java_tests_output = base / "generated-tests" / "java"
        if self.python_tests_output is None:
            self.python_tests_output = base / "generated-tests" / "python"
        if self.reports_dir is None:
            self.reports_dir = base / "reports"
        return self


class LLMConfig(BaseModel):
    provider: str = "ollama"
    base_url: str               # "auto" resolved in AgentConfig.resolve_auto_fields
    model: str
    embed_model: str = "nomic-embed-text"
    temperature: float = 0.1
    context_window: int = 8192
    request_timeout: int = 300

    @field_validator("base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        # Leave "auto" untouched; AgentConfig resolves it after EnvironmentConfig is built
        s = str(v).strip()
        return s if s == "auto" else s.rstrip("/")


class ProxyConfig(BaseModel):
    http_proxy: str = ""
    https_proxy: str = ""


class RAGConfig(BaseModel):
    chroma_path: Path = Path("auto")    # "auto" → output.base_dir/chromadb
    top_k: int = 8
    similarity_threshold: float = 0.72
    max_chunk_tokens: int = 350

    @field_validator("chroma_path", mode="before")
    @classmethod
    def expand_chroma(cls, v) -> Path:
        s = str(v).strip()
        return Path("auto") if s == "auto" else _resolve_path(s)


class CoverageConfig(BaseModel):
    target_pct: float = 90.0
    max_iterations: int = 3
    jacoco_report_path: str = "target/site/jacoco/jacoco.xml"
    pytest_cov_xml: str = "coverage.xml"


class StaticAnalysisConfig(BaseModel):
    semgrep_rules_dir: Path = Path("auto")    # "auto" → output.base_dir/semgrep-rules
    owasp_dc_data_dir: Path = Path("auto")    # "auto" → output.base_dir/nvd-data
    owasp_dc_report_dir: Path = Path("auto")  # "auto" → output.base_dir/dc-report

    @field_validator("semgrep_rules_dir", "owasp_dc_data_dir", "owasp_dc_report_dir", mode="before")
    @classmethod
    def expand_sa_paths(cls, v) -> Path:
        s = str(v).strip()
        return Path("auto") if s == "auto" else _resolve_path(s)


class ScheduleConfig(BaseModel):
    cron_expression: str = "0 2 * * 0"


class AgentConfig(BaseModel):
    system: SystemConfig = SystemConfig()
    environment: EnvironmentConfig = EnvironmentConfig()
    repos: ReposConfig
    output: OutputConfig
    llm: LLMConfig
    proxy: ProxyConfig = ProxyConfig()
    rag: RAGConfig = RAGConfig()
    coverage: CoverageConfig = CoverageConfig()
    static_analysis: StaticAnalysisConfig = StaticAnalysisConfig()
    schedule: ScheduleConfig = ScheduleConfig()

    @model_validator(mode="after")
    def resolve_auto_fields(self) -> "AgentConfig":
        env = self.environment
        base = self.output.base_dir

        # Resolve llm.base_url "auto" using the already-resolved ollama_host
        if self.llm.base_url == "auto":
            self.llm.base_url = f"http://{env.ollama_host}:{env.ollama_port}"

        # Resolve rag.chroma_path "auto"
        if str(self.rag.chroma_path) == "auto":
            self.rag.chroma_path = base / "chromadb"

        # Resolve static_analysis "auto" paths
        sa = self.static_analysis
        if str(sa.semgrep_rules_dir) == "auto":
            sa.semgrep_rules_dir = base / "semgrep-rules"
        if str(sa.owasp_dc_data_dir) == "auto":
            sa.owasp_dc_data_dir = base / "nvd-data"
        if str(sa.owasp_dc_report_dir) == "auto":
            sa.owasp_dc_report_dir = base / "dc-report"

        return self


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _find_config_yaml() -> Path:
    """Walk up from this file to locate config/config.yaml."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "config" / "config.yaml",
        here / "config" / "config.yaml",
        Path("config") / "config.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "config/config.yaml not found. Run from the code-agent/ root directory."
    )


def load_config(config_path: Path | None = None) -> AgentConfig:
    resolved = config_path or _find_config_yaml()
    with open(resolved, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    raw = _apply_env_overrides(raw)
    return AgentConfig(**raw)


@lru_cache(maxsize=1)
def get_config() -> AgentConfig:
    return load_config()


# ---------------------------------------------------------------------------
# Runtime validation
# ---------------------------------------------------------------------------

def validate_runtime(config: AgentConfig, skip_repo_check: bool = False) -> None:
    """Validate paths and Ollama reachability. Exits with code 1 on any failure."""
    plat = config.system.platform

    _INSTALL_HINTS = {
        "macos":            "brew install openjdk maven",
        "linux":            "sudo apt install openjdk-17-jdk maven",
        "windows_wsl2":     "sudo apt install openjdk-17-jdk maven  (inside WSL2)",
        "windows_native":   "Download from https://adoptium.net and https://maven.apache.org",
    }

    if not skip_repo_check:
        for label, path in [
            ("java_repo_path",   config.repos.java_repo_path),
            ("python_repo_path", config.repos.python_repo_path),
        ]:
            if not path.exists():
                hint = _INSTALL_HINTS.get(plat, "")
                LOG.error(
                    "Repo path does not exist: %s = %s\n"
                    "Edit config/config.yaml and set the correct path.\n%s",
                    label, path, hint,
                )
                sys.exit(1)

    try:
        resp = requests.get(f"{config.llm.base_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        if plat == "windows_wsl2":
            extra = (
                "WSL2 detected. The Windows host IP is auto-detected at startup.\n"
                "If it is wrong, set:  AGENT_OLLAMA_HOST=<ip>  or edit environment.ollama_host in config.yaml."
            )
        elif plat == "windows_native":
            extra = "Ensure Ollama is running — check the system tray icon."
        elif plat == "macos":
            extra = "Start Ollama with:  ollama serve  (or open the Ollama app)."
        else:
            extra = "Start Ollama with:  ollama serve"
        LOG.error(
            "Ollama is not reachable at %s.\n%s",
            config.llm.base_url, extra,
        )
        sys.exit(1)
    except requests.exceptions.Timeout:
        LOG.error(
            "Ollama connection timed out at %s. Check that Ollama is running "
            "and the base_url is correct.",
            config.llm.base_url,
        )
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        LOG.error("Ollama health check failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = get_config()
    print(cfg.model_dump_json(indent=2))
    print("\nConfig loaded successfully.")
    print(f"  Platform   : {cfg.system.platform}")
    print(f"  Ollama URL : {cfg.llm.base_url}")
    print(f"  Model      : {cfg.llm.model}")
    print(f"  Output base: {cfg.output.base_dir}")
    print(f"  ChromaDB   : {cfg.rag.chroma_path}")
