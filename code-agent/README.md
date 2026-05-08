# code-agent

Fully local AI agent that automatically analyzes two codebases (Spring Boot Java + FastAPI Python), generates JUnit 5 and pytest unit tests, runs static analysis, and produces weekly HTML+PDF reports — all on-machine using Ollama. Zero external API calls.

**Runs on Linux, macOS, WSL2 (Windows), and Windows native. All paths and Ollama connectivity are auto-configured.**

---

## Prerequisites

| Tool | Min version | Linux / WSL2 | macOS | Windows native |
| --- | --- | --- | --- | --- |
| Java | 17 | `sudo apt install openjdk-17-jdk` | `brew install openjdk` | [adoptium.net](https://adoptium.net) |
| Maven | 3.8+ | `sudo apt install maven` | `brew install maven` | [maven.apache.org](https://maven.apache.org) |
| Python | 3.11+ | `sudo apt install python3.11 python3-pip` | `brew install python` | [python.org](https://www.python.org) |
| git | any | `sudo apt install git` | `brew install git` | [git-scm.com](https://git-scm.com) |
| Ollama | latest | [ollama.com/install.sh](https://ollama.com/install.sh) | `brew install ollama` | [ollama.com](https://ollama.com) |
| dependency-check | 8.x | [DependencyCheck releases](https://github.com/jeremylong/DependencyCheck/releases) | same | same |
| semgrep | 1.x | `pip3 install semgrep` | `brew install semgrep` | `pip install semgrep` |

---

## Setup

```bash
# Inside WSL2, from the project root:
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

---

## Configuration

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
mvn test -Dagent.tests.dir=$HOME/agent-output/generated-tests/java
```

Or define it in a Maven profile in `pom.xml`:

```xml
<profiles>
  <profile>
    <id>with-agent-tests</id>
    <properties>
      <agent.tests.dir>${user.home}/agent-output/generated-tests/java</agent.tests.dir>
    </properties>
  </profile>
</profiles>
```

---

## Running the Agent

### First-time dry-run (no writes — recommended before first full run)

```bash
cd code-agent
source venv/bin/activate
python3 agent/main.py --dry-run
```

The dry-run traverses the full pipeline, logs what it would do, but writes nothing to disk and makes no ChromaDB upserts.

### Full run

```bash
source venv/bin/activate
python3 agent/main.py
```

### Run for one repo only

```bash
python3 agent/main.py --repo java
python3 agent/main.py --repo python
```

### Skip re-indexing (use existing ChromaDB index)

```bash
python3 agent/main.py --skip-ingest
```

### Skip vulnerability/logic analysis (test generation only)

```bash
python3 agent/main.py --skip-analysis
```

---

## Cron Auto-Start on Windows Boot

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

## Output

After a run, find outputs at:

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

## Module Smoke Tests

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

### "Ollama is not reachable"

- Confirm Ollama is running (`ollama serve` or check system tray on Windows)
- WSL2: the Windows host IP is auto-detected — if wrong, override with `AGENT_OLLAMA_HOST=<ip>`
- Or set `environment.ollama_host` explicitly in `config/config.yaml`

### "Repo path does not exist"

- Edit `config/config.yaml` and set `repos.java_repo_path` / `repos.python_repo_path` to your actual paths (supports `~`)

### "OWASP NVD data directory is missing or empty"

Run a one-time NVD download (requires internet):

```bash
dependency-check --updateonly --data ~/agent-output/nvd-data
```

### JaCoCo report not found

- Run `mvn jacoco:report -f /path/to/pom.xml` manually first
- Ensure the JaCoCo plugin is in `pom.xml` (see snippet above)

### Generated tests don't compile

- Check `agent-output/reports/llm-errors.log` for LLM output issues
- Verify the LLM model is pulled and responding correctly
