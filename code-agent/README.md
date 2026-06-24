# code-agent

Fully local AI agent that automatically analyzes two codebases (Spring Boot Java + FastAPI Python), generates JUnit 5 and pytest unit tests, runs static analysis, and produces weekly HTML+PDF reports — all on-machine using Ollama. Zero external API calls.

**Runs on Linux via Docker (recommended) or directly on Linux, macOS, WSL2, and Windows native.**

---

## Quick Start (Docker — Recommended for Linux)

Docker bundles every dependency (Java, Maven, OWASP Dependency-Check, Semgrep, WeasyPrint, Python environment) into a single image. Ollama runs as a companion container.

### Prerequisites

| Tool | Install |
| --- | --- |
| Docker Engine 24+ | [docs.docker.com/engine/install](https://docs.docker.com/engine/install/) |
| Docker Compose v2 | included with Docker Engine 24+ |
| Git | `sudo apt install git` |

No Java, Maven, Python, or Ollama installation needed on the host.

### 1. Clone the repository

```bash
git clone <repository-url> unit-test-generator-agent
cd unit-test-generator-agent
```

### 2. Edit docker-compose.yml

Open `docker-compose.yml` at the repo root and set the two bind-mount source paths to your actual repos:

```yaml
volumes:
  - /path/to/your/springboot-app:/repos/java:ro    # <- edit this
  - /path/to/your/fastapi-app:/repos/python:ro     # <- edit this
```

Choose a model tier by uncommenting one `AGENT_LLM_MODEL` line under the `agent` service:

```yaml
- AGENT_LLM_MODEL=codellama:7b-q4          # CPU or < 8 GB VRAM
# - AGENT_LLM_MODEL=codellama:13b-q4        # 8–23 GB VRAM
# - AGENT_LLM_MODEL=qwen2.5-coder:32b       # 24+ GB VRAM
```

For NVIDIA GPU acceleration, uncomment the `deploy.resources` block under the `ollama` service.

### 3. Build the image and run

```bash
# From the repo root (where docker-compose.yml lives):
docker compose up --build
```

On first run the entrypoint will pull the LLM model and embedding model automatically — this takes time depending on your connection. Subsequent starts are instant.

### Common Docker commands

```bash
# Dry-run — full pipeline, no files written:
docker compose run --rm agent python3 agent/main.py --dry-run

# Analyse one language only:
docker compose run --rm agent python3 agent/main.py --repo java
docker compose run --rm agent python3 agent/main.py --repo python

# Skip re-indexing (faster on repeat runs):
docker compose run --rm agent python3 agent/main.py --skip-ingest

# Skip security analysis (test generation only):
docker compose run --rm agent python3 agent/main.py --skip-analysis

# Open an interactive shell inside the agent container:
docker compose run --rm agent bash

# View streaming logs while agent runs:
docker compose logs -f agent
```

### Docker output location

Reports, generated tests, and the ChromaDB index are stored in the `agent-output` named Docker volume. To access them from the host:

```bash
# Find the volume path on disk:
docker volume inspect unit-test-generator-agent_agent-output

# Or copy a specific report out:
docker run --rm -v unit-test-generator-agent_agent-output:/data \
  alpine ls /data/reports/
```

Alternatively, change the volume in `docker-compose.yml` to a bind mount pointing at a local directory:

```yaml
- ./agent-output:/agent-output    # replaces the named volume line
```

### Weekly cron (Docker)

Add this to the host's crontab (`crontab -e`):

```
0 2 * * 0 docker compose -f /absolute/path/to/docker-compose.yml run --rm agent
```

---

## Manual Setup (Linux / macOS / WSL2 / Windows native)

Use this path if you cannot or prefer not to use Docker.

### Prerequisites

| Tool | Min version | Linux / WSL2 | macOS | Windows native |
| --- | --- | --- | --- | --- |
| Java | 17 | `sudo apt install openjdk-17-jdk` | `brew install openjdk` | [adoptium.net](https://adoptium.net) |
| Maven | 3.8+ | `sudo apt install maven` | `brew install maven` | [maven.apache.org](https://maven.apache.org) |
| Python | 3.11+ | `sudo apt install python3.11 python3-pip` | `brew install python` | [python.org](https://www.python.org) |
| git | any | `sudo apt install git` | `brew install git` | [git-scm.com](https://git-scm.com) |
| Ollama | latest | [ollama.com/install.sh](https://ollama.com/install.sh) | `brew install ollama` | [ollama.com](https://ollama.com) |
| dependency-check | 9.x | [DependencyCheck releases](https://github.com/jeremylong/DependencyCheck/releases) | same | same |
| semgrep | 1.x | `pip3 install semgrep` | `brew install semgrep` | `pip install semgrep` |

### Setup

```bash
# Inside WSL2 or Linux, from the code-agent/ directory:
bash scripts/setup.sh
```

The script will:

1. Auto-detect your platform (Linux, macOS, WSL2)
2. Verify all tools are on `PATH`
3. Auto-detect GPU VRAM and select the right model (no manual choice needed)
4. Auto-detect the Ollama host URL (WSL2 → Windows host IP, others → localhost)
5. Pull the LLM and embedding models via Ollama
6. Create a Python virtualenv and install `requirements.txt`
7. Create all output directories under `~/agent-output/` (configurable)
8. Register the weekly cron job

### Configuration

Edit `config/config.yaml` after setup:

```yaml
repos:
  java_repo_path:   "~/projects/springboot-app"   # <- EDIT THIS
  python_repo_path: "~/projects/fastapi-app"       # <- EDIT THIS

llm:
  # "auto" → Ollama host is detected at runtime (WSL2 gets Windows host IP automatically)
  # Override only if auto-detection is wrong:
  base_url: "auto"   # or "http://192.168.1.100:11434"
```

### Running the agent (manual install)

```bash
cd code-agent
source venv/bin/activate

python3 agent/main.py --dry-run     # First-time verification (no writes)
python3 agent/main.py               # Full run
python3 agent/main.py --repo java   # Java only
python3 agent/main.py --repo python # Python only
python3 agent/main.py --skip-ingest    # Skip re-indexing
python3 agent/main.py --skip-analysis  # Skip security scans
```

### Cron auto-start on Windows Boot (WSL2)

WSL2 cron does **not** start automatically when Windows boots. Choose one method:

**Option A — Windows Task Scheduler** (recommended):
1. Open Task Scheduler → Create Basic Task
2. Trigger: At log on / At startup
3. Action: Start a program
   - Program: `C:\Windows\System32\wsl.exe`
   - Arguments: `-e sudo service cron start`

**Option B — `/etc/wsl.conf`** (requires WSL2 ≥ 0.67.6 / Windows 11 build 22000+):

```ini
# /etc/wsl.conf inside WSL2
[boot]
command=service cron start
```

Verify cron is running: `service cron status`

---

## pom.xml Snippets

Add all three plugin blocks to the `<plugins>` section inside `<build>`:

### JaCoCo (Java 17 compatible)

```xml
<plugin>
  <groupId>org.jacoco</groupId>
  <artifactId>jacoco-maven-plugin</artifactId>
  <version>0.8.12</version>
  <executions>
    <execution>
      <id>prepare-agent</id>
      <goals><goal>prepare-agent</goal></goals>
    </execution>
    <execution>
      <id>report</id>
      <phase>verify</phase>
      <goals><goal>report</goal></goals>
      <configuration>
        <outputDirectory>${project.build.directory}/site/jacoco</outputDirectory>
      </configuration>
    </execution>
  </executions>
</plugin>
```

### SpotBugs + FindSecBugs

```xml
<plugin>
  <groupId>com.github.spotbugs</groupId>
  <artifactId>spotbugs-maven-plugin</artifactId>
  <version>4.8.6.6</version>
  <configuration>
    <plugins>
      <plugin>
        <groupId>com.h3xstream.findsecbugs</groupId>
        <artifactId>findsecbugs-plugin</artifactId>
        <version>1.13.0</version>
      </plugin>
    </plugins>
  </configuration>
</plugin>
```

### build-helper-maven-plugin (external test source directory)

This allows Maven to compile generated tests from outside the repo without replacing your existing `src/test/java/`:

```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>build-helper-maven-plugin</artifactId>
  <version>3.6.0</version>
  <executions>
    <execution>
      <id>add-agent-test-source</id>
      <phase>generate-test-sources</phase>
      <goals><goal>add-test-source</goal></goals>
      <configuration>
        <sources>
          <source>${agent.tests.dir}</source>
        </sources>
      </configuration>
    </execution>
  </executions>
</plugin>
```

When running Maven manually with generated tests, pass the property:

```bash
# Manual install (tests are in ~/agent-output):
mvn test -Dagent.tests.dir=$HOME/agent-output/generated-tests/java

# Docker (tests are in the agent-output volume, copy them out first):
docker run --rm -v unit-test-generator-agent_agent-output:/data \
  alpine tar -cC /data/generated-tests/java . | tar -xC /tmp/agent-java-tests
mvn test -Dagent.tests.dir=/tmp/agent-java-tests
```

---

## Output

### Docker

Reports and generated tests live in the `agent-output` Docker named volume. Copy reports to your host:

```bash
# List reports:
docker run --rm -v unit-test-generator-agent_agent-output:/data alpine ls /data/reports/

# Copy the latest HTML report to your current directory:
docker run --rm -v unit-test-generator-agent_agent-output:/data \
  alpine cat /data/reports/$(docker run --rm \
    -v unit-test-generator-agent_agent-output:/data \
    alpine ls /data/reports/ | grep .html | tail -1) > latest-report.html
```

Or switch to a bind mount (see Docker Quick Start above) so reports appear directly in a host folder.

### Manual install

```
~/agent-output/
├── reports/
│   ├── 2025-W22-report.html   ← Full weekly report (open in browser)
│   ├── 2025-W22-report.pdf    ← PDF version
│   ├── run_history.json       ← Historical trend data
│   ├── llm-errors.log         ← LLM parse failures (check if issues arise)
│   └── run.log                ← Cron run stdout/stderr
├── generated-tests/
│   ├── java/                  ← Generated JUnit 5 test files
│   └── python/                ← Generated pytest test files
└── chromadb/                  ← Persistent vector index
```

### Reading the report

Open `*-report.html` in any browser. Sections:
1. **Run Summary** — status badge, model, duration, coverage averages
2. **Coverage Overview** — per-class/file coverage with delta from previous run
3. **4-Week Trend** — inline SVG coverage trend chart
4. **Vulnerability Findings** — SpotBugs, OWASP DC, Bandit, Semgrep findings by severity
5. **Logic Error Findings** — LLM-identified logic issues with suggested fixes
6. **Generated Test Files** — what was written and coverage improvement achieved
7. **Run Issues** — any partial failures logged during the run

---

## Module Smoke Tests (manual install only)

Each module can be run independently to verify it works in isolation:

```bash
source venv/bin/activate

python3 agent/config.py
python3 agent/ingestion/chunker.py
python3 agent/ingestion/embedder.py
python3 agent/ingestion/indexer.py
python3 agent/analysis/vulnerability.py
python3 agent/analysis/logic_errors.py
python3 agent/analysis/coverage.py
python3 agent/testgen/java_gen.py
python3 agent/testgen/python_gen.py
python3 agent/testgen/coverage_loop.py
python3 agent/reporting/renderer.py
```

---

## Troubleshooting

### "Ollama is not reachable" (Docker)

- Confirm the `ollama` service is running: `docker compose ps`
- The agent container connects to Ollama via the service name `ollama` — this is set by `AGENT_OLLAMA_HOST=ollama` in `docker-compose.yml`. Do not change it.
- If Ollama crashed, restart it: `docker compose restart ollama`
- Check Ollama logs: `docker compose logs ollama`

### "Ollama is not reachable" (manual install)

- Confirm Ollama is running (`ollama serve` or check system tray on Windows)
- WSL2: the Windows host IP is auto-detected — if wrong, override with `AGENT_OLLAMA_HOST=<ip>`
- Or set `environment.ollama_host` explicitly in `config/config.yaml`

### "Repo path does not exist" (Docker)

- The paths inside the container are `/repos/java` and `/repos/python`, controlled by the volume lines in `docker-compose.yml`
- Check that the host paths in the volume bind-mounts actually exist on your machine
- Verify: `docker compose run --rm agent ls /repos/java`

### "Repo path does not exist" (manual install)

- Edit `config/config.yaml` and set `repos.java_repo_path` / `repos.python_repo_path` to your actual paths (supports `~`)

### "OWASP NVD data directory is missing or empty"

**Docker:** Run a one-time NVD download into the volume:

```bash
docker compose run --rm agent \
  dependency-check --updateonly --data /agent-output/nvd-data
```

**Manual install:**

```bash
dependency-check --updateonly --data ~/agent-output/nvd-data
```

### JaCoCo report not found

- Run `mvn jacoco:report -f /path/to/pom.xml` manually first
- Ensure the JaCoCo plugin is in `pom.xml` (see snippet above)

### Docker image build fails at OWASP Dependency-Check download

The build downloads the DC zip from GitHub. If your build machine has no internet access,
build with `--build-arg DC_VERSION=` pointing to a version you've pre-mirrored, or remove
that `RUN` block and install DC manually via the volume.

### Generated tests don't compile

- Check `agent-output/reports/llm-errors.log` for LLM output issues
- Verify the LLM model is pulled and responding correctly
