# Complete Setup Guide — Code-Agent Unit Test Generator

> **Who is this guide for?**
> This guide is written for anyone — even if you have never set up a software project before.
> Every step is explained in plain language. Follow the steps in order and you will have the
> agent running by the end.

---


## Table of Contents

1. [What Does This Software Do?](#1-what-does-this-software-do)
2. [What Does Your Computer Need?](#2-what-does-your-computer-need)
3. [Choose Your Setup Method](#3-choose-your-setup-method)
4. [Docker Setup (Recommended for Linux)](#4-docker-setup-recommended-for-linux)
5. [Manual Setup — Install Java (JDK 17)](#5-manual-setup--install-java-jdk-17)
6. [Manual Setup — Install Maven](#6-manual-setup--install-maven)
7. [Manual Setup — Install Python 3.11](#7-manual-setup--install-python-311)
8. [Manual Setup — Install Git](#8-manual-setup--install-git)
9. [Manual Setup — Install Ollama (The AI Brain)](#9-manual-setup--install-ollama-the-ai-brain)
10. [Manual Setup — Install dependency-check (Security Scanner)](#10-manual-setup--install-dependency-check-security-scanner)
11. [Manual Setup — Install Semgrep (Code Pattern Scanner)](#11-manual-setup--install-semgrep-code-pattern-scanner)
12. [Download This Project](#12-download-this-project)
13. [Run the Setup Script (Manual only)](#13-run-the-setup-script-manual-only)
14. [Tell the Agent Where Your Code Is](#14-tell-the-agent-where-your-code-is)
15. [Prepare Your Java Project (pom.xml Changes)](#15-prepare-your-java-project-pomxml-changes)
16. [Build the RAG Knowledge Base (ChromaDB)](#16-build-the-rag-knowledge-base-chromadb)
17. [Run Your First Dry-Run](#17-run-your-first-dry-run)
18. [Run the Full Pipeline](#18-run-the-full-pipeline)
19. [Understanding the Output and Reports](#19-understanding-the-output-and-reports)
20. [Schedule Automatic Weekly Runs](#20-schedule-automatic-weekly-runs)
21. [Troubleshooting Common Problems](#21-troubleshooting-common-problems)
22. [Quick Reference Card](#22-quick-reference-card)

---

## 1. What Does This Software Do?

Imagine you have written a large Java application. Normally, a developer has to manually write
"tests" — small programs that check whether each part of your code works correctly. This is
time-consuming and often skipped.

**This agent does it automatically.** Every week it:

1. **Reads your code** — it understands your Java (and Python) code like a developer would
2. **Finds weaknesses** — it scans for security problems and logic bugs
3. **Writes tests** — it uses a local AI to write JUnit test cases for your code
4. **Measures coverage** — it checks what percentage of your code is tested (target: 90%)
5. **Generates a report** — a beautiful HTML/PDF report showing everything it found

Everything runs **on your computer** — no data is sent to the internet. The AI model runs
locally using a free tool called Ollama.

---

## 2. What Does Your Computer Need?

### Minimum Hardware

| Component | Minimum | Recommended |
| --- | --- | --- |
| RAM | 8 GB | 16 GB |
| Storage | 30 GB free | 50 GB free |
| CPU | Any modern 4-core | 8-core or more |
| GPU (optional) | None needed | NVIDIA with 8+ GB VRAM |

> **No GPU?** The agent will still work — it just runs slower. A full analysis run may take
> 2–6 hours on CPU vs. 15–30 minutes with a GPU.

### Operating System

- **Linux** (Ubuntu 20.04+ or similar) — recommended, works with Docker or manual install
- **macOS** (12 Monterey or later) — manual install only
- **Windows with WSL2** — manual install inside WSL2 (recommended for Windows users)
- **Windows Native** — manual install only

---

## 3. Choose Your Setup Method

There are two ways to get the agent running. Choose one:

### Option A: Docker (Recommended for Linux users)

Docker packages everything the agent needs — Java, Maven, Python, OWASP Dependency-Check,
Semgrep, WeasyPrint — into a single container image. You only need to install Docker.

**Choose Docker if:**
- You are on Linux
- You want the simplest setup with the fewest steps
- You do not want to install Java, Maven, or Python on your host machine

**Skip to:** [Section 4 — Docker Setup](#4-docker-setup-recommended-for-linux)

---

### Option B: Manual Install

Install each tool individually. Works on Linux, macOS, WSL2 (Windows), and Windows native.

**Choose manual install if:**
- You are on macOS or Windows
- You already have Java, Maven, and Python installed
- You prefer not to use Docker

**Continue to:** [Section 5 — Manual Setup](#5-manual-setup--install-java-jdk-17)

---

## 4. Docker Setup (Recommended for Linux)

This section replaces Sections 5–13 for Docker users. If you are doing a manual install,
skip to [Section 5](#5-manual-setup--install-java-jdk-17).

### Step 4.1 — Install Docker Engine

```bash
# Ubuntu / Debian:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) \
    signed-by=/etc/apt/keyrings/docker.asc] \
    https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin -y
```

Allow your user to run Docker without `sudo` (log out and back in after this):

```bash
sudo usermod -aG docker $USER
```

Verify Docker is working:

```bash
docker --version        # should print Docker version 24+
docker compose version  # should print Docker Compose version 2+
```

### Step 4.2 — Download This Project

```bash
git clone https://github.com/neerajr/unit-test-generator-agent.git unit-test-generator-agent
cd unit-test-generator-agent
```


### Step 4.3 — Edit docker-compose.yml

Open `docker-compose.yml` (in the root of the project) with any text editor:

```bash
nano docker-compose.yml    # or use VS Code, gedit, etc.
```

Find the two lines that say `/path/to/your/...` and change them to the actual paths
on your computer where your Java and Python projects live:

```yaml
volumes:
  - /home/yourname/projects/springboot-app:/repos/java:ro    # <- edit this
  - /home/yourname/projects/fastapi-app:/repos/python:ro     # <- edit this
```

> The `:ro` at the end means "read-only" — the agent will never modify your source code.

Also choose the right AI model based on your hardware (uncomment one line):

```yaml
environment:
  - AGENT_LLM_MODEL=codellama:7b-q4          # CPU or < 8 GB GPU VRAM (default)
  # - AGENT_LLM_MODEL=codellama:13b-q4        # 8–23 GB GPU VRAM
  # - AGENT_LLM_MODEL=qwen2.5-coder:32b       # 24+ GB GPU VRAM
```

**If you have an NVIDIA GPU**, also uncomment the `deploy.resources` block under the
`ollama` service to enable GPU acceleration:

```yaml
ollama:
  ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

### Step 4.4 — Build the Docker Image

From the project root (where `docker-compose.yml` is located):

```bash
docker compose build
```

This downloads the base image and installs all dependencies inside the container.
It takes 5–15 minutes and only needs to be done once (or when you update the project).

**What gets installed automatically inside the image:**
- Python 3.11 + all Python libraries
- OpenJDK 17 + Maven
- OWASP Dependency-Check CLI
- Semgrep, Bandit (static analysis tools)
- WeasyPrint (HTML to PDF renderer with all its fonts and graphics libraries)

### Step 4.5 — First Run (Dry-Run)

Start everything with a dry-run first. This confirms the containers can talk to each other
and the agent can find your code — without writing any test files yet.

```bash
docker compose run --rm agent python3 agent/main.py --dry-run
```

The first time you run this:
1. Docker starts the Ollama container
2. The entrypoint script waits for Ollama to be ready (may take 30–60 seconds)
3. It automatically downloads the LLM model (~4 GB) and embedding model (~270 MB)
4. The agent runs in dry-run mode

**This step requires a good internet connection and may take 20–60 minutes** because of
the model download. After the first run the models are cached in the `ollama-models` volume
and subsequent starts are instant.

You should see output like:

```
[entrypoint] Waiting for Ollama at http://ollama:11434...
[entrypoint] Ollama is ready.
[entrypoint] Pulling codellama:7b-q4 — this may take a while...
[entrypoint] Pull complete: codellama:7b-q4
[entrypoint] Pulling nomic-embed-text...
[entrypoint] Pull complete: nomic-embed-text
[entrypoint] Starting: python3 agent/main.py --dry-run
...
[INFO]  Platform: linux
[INFO]  Ollama reachable at http://ollama:11434
[INFO]  Java repo: /repos/java  ✓ exists
[INFO]  Dry-run complete. No files written.
```

**If you see "Repo path does not exist"**, check that the host paths in your volume
bind-mounts exist and are correct. Test with:

```bash
docker compose run --rm agent ls /repos/java
```

### Step 4.6 — Full Run

Once the dry-run succeeds, run the full pipeline:

```bash
docker compose up
```

Or in the background:

```bash
docker compose up -d
docker compose logs -f agent    # follow the logs
```

### Step 4.7 — Access Your Reports

Reports are saved in the `agent-output` Docker named volume. The easiest way to access
them is to switch to a bind mount — edit the agent's volume in `docker-compose.yml`:

```yaml
# Replace this line:
- agent-output:/agent-output

# With a local folder path:
- ./agent-output:/agent-output
```

After making this change and running again, reports will appear in a new `agent-output/`
folder right next to your `docker-compose.yml` file.

Open the report in your browser:

```bash
xdg-open ./agent-output/reports/*.html
```

**Docker users continue to Section 14** to configure your Java project's pom.xml.

> Sections 5–13 (manual tool installation and the setup script) are **not needed** when
> using Docker. Skip directly to [Section 14](#14-tell-the-agent-where-your-code-is).

---

## 5. Manual Setup — Install Java (JDK 17)

Java is needed to analyze and test your Spring Boot project.

### Linux / WSL2

Open a terminal and run:

```bash
sudo apt update
sudo apt install openjdk-17-jdk -y
```

Verify it worked:

```bash
java -version
```

You should see something like: `openjdk version "17.0.x"`

### macOS

```bash
brew install openjdk@17
# Make Java available system-wide:
sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk
```

> If you don't have Homebrew, install it first: go to [brew.sh](https://brew.sh) and follow the instructions (one-liner command).

### Windows Native

1. Go to [adoptium.net](https://adoptium.net)
2. Click **Latest LTS** and download the **JDK 17** installer for Windows
3. Run the installer — accept all defaults
4. Verify: open PowerShell and run `java -version`

---

## 6. Manual Setup — Install Maven

Maven is a build tool for Java projects. The agent uses it to compile and run your tests.

### Linux / WSL2

```bash
sudo apt install maven -y
```

Verify:

```bash
mvn --version
```

You should see: `Apache Maven 3.x.x`

### macOS

```bash
brew install maven
```

### Windows Native

1. Go to [maven.apache.org/download.cgi](https://maven.apache.org/download.cgi)
2. Download the **Binary zip archive** (e.g., `apache-maven-3.9.x-bin.zip`)
3. Extract it to a folder, e.g., `C:\Program Files\Maven`
4. Add Maven to your PATH:
   - Search "Environment Variables" in the Windows Start menu
   - Click "Environment Variables"
   - Under "System variables", find `Path` → click Edit
   - Click New → add `C:\Program Files\Maven\bin`
   - Click OK on all windows
5. Open a new PowerShell window and run `mvn --version`

---

## 7. Manual Setup — Install Python 3.11

Python runs the agent itself.

### Linux / WSL2

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y
```

Verify:

```bash
python3 --version
```

Should show: `Python 3.11.x`

### macOS

```bash
brew install python@3.11
```

### Windows Native

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download Python **3.11.x** (not 3.12+ yet)
3. Run the installer
4. **Important:** Check the box **"Add Python to PATH"** before clicking Install
5. Verify: open a new PowerShell and run `python --version`

---

## 8. Manual Setup — Install Git

Git is used to read file history and detect which files changed since last run.

### Linux / WSL2

```bash
sudo apt install git -y
```

### macOS

```bash
brew install git
```

### Windows Native

1. Go to [git-scm.com/download/win](https://git-scm.com/download/win)
2. Download and run the installer
3. Accept all defaults during installation
4. Verify: open a new PowerShell and run `git --version`

---

## 9. Manual Setup — Install Ollama (The AI Brain)

Ollama is the software that runs the AI language model on your computer. This is what
generates the test cases.

### Linux / WSL2

Run this one-line installer:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start Ollama in the background:

```bash
ollama serve &
```

### macOS

```bash
brew install ollama
# Or download the app from https://ollama.com
```

Start Ollama:

```bash
ollama serve
# Or open the Ollama app from Applications
```

### Windows Native

1. Go to [ollama.com](https://ollama.com) and download the Windows installer
2. Run the installer — it adds Ollama to your system tray
3. Ollama starts automatically at login

### WSL2 Special Note

If you are using WSL2, **Ollama should run on the Windows side** (not inside WSL2).
The setup script will automatically detect the Windows host IP address and connect to it.
You just need to make sure the Ollama app is running on Windows before running the agent.

### Verify Ollama is Working

After installing, test it from your terminal:

```bash
# Linux/macOS/WSL2:
curl http://localhost:11434/api/tags

# Windows (PowerShell):
Invoke-RestMethod http://localhost:11434/api/tags
```

If you see a JSON response, Ollama is working.

---

## 10. Manual Setup — Install dependency-check (Security Scanner)

This tool scans your Java project for known security vulnerabilities in libraries.

> **Docker users:** dependency-check v9.2.0 is pre-installed in the Docker image. Skip this section.

### All platforms

1. Go to [github.com/jeremylong/DependencyCheck/releases](https://github.com/jeremylong/DependencyCheck/releases)
2. Download the latest `dependency-check-x.x.x-release.zip`
3. Extract it somewhere, e.g.:
   - Linux/WSL2/macOS: `~/tools/dependency-check/`
   - Windows: `C:\tools\dependency-check\`

4. Add `dependency-check/bin/` to your PATH:

   **Linux/macOS** — add to `~/.bashrc` or `~/.zshrc`:
   ```bash
   export PATH="$HOME/tools/dependency-check/bin:$PATH"
   ```
   Then run: `source ~/.bashrc`

   **Windows** — same PATH steps as Maven above, pointing to `C:\tools\dependency-check\bin`

5. Verify:
   ```bash
   dependency-check --version
   ```

### Download the NVD Vulnerability Database (One-time, ~2 GB)

The tool needs a local copy of the National Vulnerability Database. Run this once
(requires internet, takes 5–15 minutes):

```bash
dependency-check --updateonly --data ~/agent-output/nvd-data
```

> **Windows (PowerShell):**
> ```powershell
> dependency-check --updateonly --data "$env:USERPROFILE\agent-output\nvd-data"
> ```

---

## 11. Manual Setup — Install Semgrep (Code Pattern Scanner)

Semgrep scans your code for security patterns.

> **Docker users:** Semgrep is pre-installed in the Docker image. Skip this section.

### Linux / WSL2 / macOS

```bash
pip3 install semgrep
```

### Windows Native

```powershell
pip install semgrep
```

Verify:

```bash
semgrep --version
```

---

## 12. Download This Project

### Option A: Using Git (recommended)

```bash
git clone <repository-url> unit-test-generator-agent
cd unit-test-generator-agent/code-agent
```

> Replace `<repository-url>` with the actual URL of this repository.

### Option B: Download as ZIP

1. Download the ZIP file from the repository
2. Extract it to a folder, e.g., `~/unit-test-generator-agent` (Linux/Mac) or `C:\unit-test-generator-agent` (Windows)
3. Open a terminal and navigate to the `code-agent` sub-folder:
   ```bash
   cd ~/unit-test-generator-agent/code-agent        # Linux/macOS
   cd C:\unit-test-generator-agent\code-agent        # Windows PowerShell
   ```

---

## 13. Run the Setup Script (Manual only)

> **Docker users:** skip this section. Your setup is complete after Section 4.

The setup script does all the heavy lifting automatically: it detects your GPU,
downloads the right AI model, creates a Python environment, and prepares the output folders.

### Linux / WSL2 / macOS

Make sure you are inside the `code-agent/` folder, then run:

```bash
bash scripts/setup.sh
```

**What the script does (step by step):**

1. Detects your platform (Linux, macOS, WSL2)
2. Reads the output directory from `config/config.yaml`
3. Checks all required tools are installed
4. Detects your GPU VRAM and picks the right AI model:
   - GPU with 24+ GB → picks the best quality model (`qwen2.5-coder:32b`)
   - GPU with 8–23 GB → picks a good model (`codellama:13b-q4`)
   - No GPU / CPU only → picks a lighter model (`codellama:7b-q4`) — still works!
5. Downloads the AI model through Ollama (~4–20 GB depending on model)
6. Downloads the embedding model (`nomic-embed-text`, ~270 MB)
7. Creates a Python virtual environment in `venv/`
8. Installs all Python libraries from `requirements.txt`
9. Creates all output folders under `~/agent-output/`
10. Downloads Semgrep rules for OWASP Top 10 security checks
11. Registers the weekly cron job (Sunday 2:00 AM)

**Expected time:** 20–60 minutes (most time is downloading the AI model)

### Windows Native (PowerShell)

```powershell
pwsh -ExecutionPolicy Bypass -File scripts\setup.ps1
```

> If `pwsh` is not found, install PowerShell 7 from the Microsoft Store or
> [github.com/PowerShell/PowerShell/releases](https://github.com/PowerShell/PowerShell/releases).

---

## 14. Tell the Agent Where Your Code Is

### Docker users

Edit the volume bind-mounts in `docker-compose.yml`:

```yaml
volumes:
  - /home/yourname/projects/springboot-app:/repos/java:ro    # <- change the left side
  - /home/yourname/projects/fastapi-app:/repos/python:ro     # <- change the left side
```

The right-hand side (`/repos/java` and `/repos/python`) is fixed — the agent always
looks at those paths inside the container. Only change the left side (your host paths).

Verify the agent can see your repos:

```bash
docker compose run --rm agent ls /repos/java
docker compose run --rm agent ls /repos/python
```

### Manual install users

Open `config/config.yaml` in any text editor (Notepad, VS Code, nano, etc.).

Find the `repos` section near the top:

```yaml
repos:
  java_repo_path:   "~/projects/springboot-app"   # <- EDIT THIS
  python_repo_path: "~/projects/fastapi-app"       # <- EDIT THIS
```

Change these two paths to point to your actual code:

**Example — Linux / WSL2 / macOS:**

```yaml
repos:
  java_repo_path:   "~/my-company/inventory-service"
  python_repo_path: "~/my-company/api-service"
```

**Example — Windows Native:**

```yaml
repos:
  java_repo_path:   "C:/Users/YourName/projects/inventory-service"
  python_repo_path: "C:/Users/YourName/projects/api-service"
```

> Use forward slashes `/` even on Windows. The `~` symbol means "your home folder"
> and works automatically.

### What if you only have a Java project?

Run the agent with `--repo java` (explained in Section 18). Set any path for the
unused language — the agent skips repos it cannot find when a `--repo` flag is used.

---

## 15. Prepare Your Java Project (pom.xml Changes)

Your Spring Boot project needs three Maven plugins so the agent can:
- Measure how much of your code is covered by tests (JaCoCo)
- Scan for bugs (SpotBugs)
- Include the agent-generated tests without overwriting your existing tests (build-helper)

Open your project's `pom.xml` file and find the `<plugins>` section inside `<build>`.
Add the following three blocks inside `<plugins>`:

### Plugin 1 — JaCoCo (Test Coverage Measurement)

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

### Plugin 2 — SpotBugs with FindSecBugs (Bug and Security Scanner)

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

### Plugin 3 — build-helper (Include Agent-Generated Tests)

This plugin allows the agent's generated test files to be compiled and run by Maven
**without touching your existing tests**.

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

### Verify the pom.xml Changes Work

Run this command inside your Java project folder:

```bash
mvn test jacoco:report -q
```

After it finishes, check that this file was created:

```
your-java-project/target/site/jacoco/jacoco.xml
```

If the file exists, JaCoCo is working correctly.

---

## 16. Build the RAG Knowledge Base (ChromaDB)

RAG stands for **Retrieval-Augmented Generation**. Think of it as giving the AI a
"library card" — before generating tests, the AI searches a local database of your code
to understand context (what classes exist, how methods call each other, etc.).

This database is called **ChromaDB** and it lives in the agent's output directory
(`~/agent-output/chromadb/` for manual install, or the `agent-output` volume for Docker).

### How the RAG system works

```
Your Code Files
      ↓
  Chunker: Breaks code into methods/functions (using tree-sitter AST parser)
      ↓
  Embedder: Converts each chunk into a number pattern (vector) via Ollama
      ↓
  ChromaDB: Stores all chunks + their vectors on disk
      ↓
  At test-generation time: Agent searches ChromaDB for relevant code context
      ↓
  AI generates better tests because it understands your whole codebase
```

### First-time indexing

The indexing happens **automatically** the first time you run the agent. There is nothing
extra to do.

To build only the database without running the full pipeline:

```bash
# Docker:
docker compose run --rm agent python3 agent/main.py --dry-run --skip-analysis

# Manual install:
source venv/bin/activate
python3 agent/main.py --dry-run --skip-analysis
```

### How the database stays up-to-date

On every subsequent run, the agent only re-indexes files that **changed since the last run**
(detected via `git diff`). This makes subsequent runs much faster.

---

## 17. Run Your First Dry-Run

A **dry-run** does everything except actually write test files or reports. Use it to
verify that the agent can connect to all the tools and read your code.

### Docker

```bash
docker compose run --rm agent python3 agent/main.py --dry-run
```

### Manual install

```bash
# Linux / macOS / WSL2:
cd ~/unit-test-generator-agent/code-agent
source venv/bin/activate
python3 agent/main.py --dry-run

# Windows Native (PowerShell):
cd C:\unit-test-generator-agent\code-agent
venv\Scripts\activate.ps1
python agent\main.py --dry-run
```

### What a successful dry-run looks like

```
[INFO]  Loading configuration...
[INFO]  Platform: linux
[INFO]  Ollama reachable at http://ollama:11434   (Docker) or http://localhost:11434 (manual)
[INFO]  Model: codellama:7b-q4
[INFO]  Java repo: /repos/java  ✓ exists           (Docker) or ~/your/path ✓ exists (manual)
[INFO]  Step 1/9 — Indexing Java repo...
[INFO]    Chunked 127 methods from 34 Java files
[INFO]    [dry-run] Would upsert 127 chunks to ChromaDB
[INFO]  ...
[INFO]  Dry-run complete. No files written.
```

### Common dry-run failures and fixes

**"Repo path does not exist" (Docker)**
→ Your volume bind-mount path is wrong. Check the host path in `docker-compose.yml` exists.
Test: `docker compose run --rm agent ls /repos/java`

**"Repo path does not exist" (manual)**
→ Check `config/config.yaml` — the path you entered does not exist. Check for typos.

**"Ollama is not reachable" (Docker)**
→ The `ollama` service may still be starting. Wait 30 seconds and retry.
Check: `docker compose ps ollama`

**"Ollama is not reachable" (manual)**
→ Ollama is not running. Start it: `ollama serve` (Linux/macOS) or open the Ollama app (Windows).

**"java: command not found" or "mvn: command not found" (manual only)**
→ Java or Maven is not installed correctly, or not in your PATH. Redo Sections 5 and 6.

---

## 18. Run the Full Pipeline

Once the dry-run succeeds, run the full pipeline:

### Docker

```bash
docker compose up
```

### Manual install

```bash
# Linux / macOS / WSL2:
python3 agent/main.py

# Windows Native:
python agent\main.py
```

### What happens during a full run

The agent runs 9 steps in sequence:

| Step | What it does | Time (estimate) |
| --- | --- | --- |
| 1 — Index | Reads and understands your code | 5–20 min (first run) |
| 2 — SpotBugs | Scans Java for bugs | 2–10 min |
| 3 — OWASP DC | Checks libraries for vulnerabilities | 5–15 min |
| 4 — Bandit | Scans Python for security issues | 1–2 min |
| 5 — Semgrep | Pattern-based code scan | 2–5 min |
| 6 — Logic analysis | AI finds logic bugs | 10–30 min |
| 7 — Java test gen | AI writes JUnit tests | 30–120 min |
| 8 — Python test gen | AI writes pytest tests | 20–60 min |
| 9 — Report | Creates HTML + PDF report | 1–2 min |

### Running for one language only

```bash
# Docker:
docker compose run --rm agent python3 agent/main.py --repo java
docker compose run --rm agent python3 agent/main.py --repo python

# Manual:
python3 agent/main.py --repo java
python3 agent/main.py --repo python
```

### Skipping steps (faster subsequent runs)

```bash
# Skip re-indexing (if your code has not changed):
docker compose run --rm agent python3 agent/main.py --skip-ingest    # Docker
python3 agent/main.py --skip-ingest                                   # Manual

# Skip security analysis (test generation only):
docker compose run --rm agent python3 agent/main.py --skip-analysis  # Docker
python3 agent/main.py --skip-analysis                                  # Manual
```

---

## 19. Understanding the Output and Reports

### Docker — accessing reports

By default reports live in the `agent-output` Docker named volume. To access them
easily, switch the volume to a bind mount in `docker-compose.yml`:

```yaml
# Change this line under the agent service volumes:
- agent-output:/agent-output

# To a local folder:
- ./agent-output:/agent-output
```

After this change, reports appear in `agent-output/reports/` next to your `docker-compose.yml`.

### Manual install — output location

```
~/agent-output/
├── reports/
│   ├── 2025-W22-report.html    ← Main weekly report (open in browser)
│   ├── 2025-W22-report.pdf     ← Same report as PDF
│   ├── run_history.json        ← Tracks coverage over time
│   └── run.log                 ← Log of the last scheduled run
├── generated-tests/
│   ├── java/                   ← Generated JUnit 5 test files
│   └── python/                 ← Generated pytest test files
└── chromadb/                   ← The RAG knowledge database (do not delete)
```

### How to view the report

**On Linux (Docker or manual):**
```bash
xdg-open ~/agent-output/reports/2025-W22-report.html
```

**On macOS:**
```bash
open ~/agent-output/reports/2025-W22-report.html
```

**On Windows (File Explorer):**
Navigate to `C:\Users\YourName\agent-output\reports\` and double-click the `.html` file.

### What the report contains

The report has seven sections:

**1. Run Summary** — A status badge (green = success, yellow = partial, red = failed),
the AI model used, total run duration, and how many issues were found.

**2. Coverage Overview** — A table showing every Java class and Python file with:
- How many lines are currently tested (%)
- How much coverage improved compared to last week (delta)
- Color coding: red = below target, yellow = close, green = at target

**3. 4-Week Trend Chart** — A line graph showing whether your coverage is improving
week over week. You want this line to go up over time.

**4. Vulnerability Findings** — Security and bug findings from the four scanners,
sorted from most serious (HIGH) to least (INFO).

**5. Logic Error Findings** — AI-detected logic bugs like:
- Possible null pointer errors
- Missing transaction boundaries
- Race conditions
- Incorrect error handling

**6. Generated Test Files** — A list of every test file the agent wrote, showing
how much each one improved your coverage.

**7. Run Issues** — Any errors or warnings that occurred during the run.

### Running generated tests manually

```bash
# Manual install:
cd ~/my-company/inventory-service
mvn test jacoco:report -Dagent.tests.dir=$HOME/agent-output/generated-tests/java

# Docker (if using bind mount ./agent-output):
cd ~/my-company/inventory-service
mvn test jacoco:report -Dagent.tests.dir=$(pwd)/../agent-output/generated-tests/java
```

---

## 20. Schedule Automatic Weekly Runs

### Docker — host crontab

Add this to the host crontab (`crontab -e`):

```
0 2 * * 0 docker compose -f /absolute/path/to/docker-compose.yml run --rm agent
```

Change `/absolute/path/to/docker-compose.yml` to the actual path on your system. The
`ollama` service must already be running (start it once with `docker compose up -d ollama`).

To auto-start Ollama when the machine boots, add the `restart: unless-stopped` line
(it is already there by default in the provided `docker-compose.yml`) and enable the
Docker service to start on boot:

```bash
sudo systemctl enable docker
```

### Manual install — Linux / WSL2 — Using cron

The setup script already registered the cron job. To verify:

```bash
crontab -l
```

You should see a line like:
```
0 2 * * 0 /home/yourname/unit-test-generator-agent/code-agent/scripts/run_agent.sh >> ...
```

To change the schedule, edit `config/config.yaml`:

```yaml
schedule:
  cron_expression: "0 2 * * 0"   # Format: minute hour day month weekday
                                  # "0 2 * * 0" = Sunday at 02:00 AM
                                  # "0 8 * * 1" = Monday at 08:00 AM
```

Then re-run `bash scripts/setup.sh` to update the cron job.

**WSL2 only — make cron start automatically on Windows boot:**

```bash
sudo nano /etc/wsl.conf
```

Add these lines:

```ini
[boot]
command=service cron start
```

Save with `Ctrl+O`, exit with `Ctrl+X`. Restart WSL2 for this to take effect.

### Manual install — macOS — Using cron

```bash
crontab -e
```

Add this line:

```
0 2 * * 0 /Users/yourname/unit-test-generator-agent/code-agent/scripts/run_agent.sh >> /Users/yourname/agent-output/reports/run.log 2>&1
```

### Manual install — Windows Native — Using Task Scheduler

Open an elevated PowerShell (right-click → Run as administrator) and run:

```powershell
$Action  = New-ScheduledTaskAction -Execute "pwsh" -Argument "-File `"C:\unit-test-generator-agent\code-agent\scripts\run_agent.ps1`""
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "CodeAgent" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest
```

---

## 21. Troubleshooting Common Problems

### "Ollama is not reachable" (Docker)

The agent container cannot reach the Ollama sidecar.

**Fix:**
1. Check that both containers are running: `docker compose ps`
2. Restart Ollama if it crashed: `docker compose restart ollama`
3. Check Ollama logs: `docker compose logs ollama`
4. The agent uses `AGENT_OLLAMA_HOST=ollama` to reach Ollama via Docker's internal DNS.
   Do not change this value.

---

### "Ollama is not reachable" (manual install)

The agent cannot connect to the AI model.

**Fix:**
1. Make sure Ollama is running:
   - Linux/macOS: Run `ollama serve` in a terminal (keep it open)
   - Windows: Open the Ollama app from the Start menu
2. Test the connection:
   ```bash
   curl http://localhost:11434/api/tags
   ```
3. WSL2 users: The Windows host IP is detected automatically. If it seems wrong:
   ```bash
   export AGENT_OLLAMA_HOST=<your-windows-ip>
   python3 agent/main.py --dry-run
   ```

---

### "Repo path does not exist" (Docker)

**Fix:**
1. Check the host path in your `docker-compose.yml` volume line actually exists on your machine
2. Test: `docker compose run --rm agent ls /repos/java`
3. If empty or missing, correct the host path and rebuild

---

### "Repo path does not exist" (manual install)

**Fix:**
1. Check the path exists: `ls ~/my-company/inventory-service`
2. If not found: `find ~ -name "pom.xml" 2>/dev/null` to locate your Java project
3. Update `config/config.yaml` with the correct path

---

### "JaCoCo report not found" or "jacoco.xml is missing"

**Fix:**
1. Check that the JaCoCo plugin is in your `pom.xml` (see Section 15)
2. Run Maven manually:
   ```bash
   cd ~/my-company/inventory-service
   mvn test jacoco:report
   ```
3. Check that this file was created: `ls target/site/jacoco/jacoco.xml`

---

### "Model not found" or "model not loaded" (Docker)

**Fix:**
The entrypoint should have pulled the model automatically. Check the logs:

```bash
docker compose logs agent | head -50
```

If the pull failed (e.g., network timeout), pull manually:

```bash
docker compose run --rm agent bash -c \
  'curl -X POST http://ollama:11434/api/pull \
   -d "{\"name\":\"${AGENT_LLM_MODEL}\",\"stream\":false}" \
   --max-time 1800'
```

---

### "Model not found" or "model not loaded" (manual install)

**Fix:** Pull the model manually:

```bash
ollama pull codellama:7b-q4       # CPU model
ollama pull codellama:13b-q4      # GPU 8 GB+ model
ollama pull nomic-embed-text      # Embedding model (always required)
```

List downloaded models: `ollama list`

---

### "SpotBugs: BUILD FAILURE"

**Fix:**
1. Check that SpotBugs plugin is in your `pom.xml` (see Section 15)
2. Run SpotBugs manually to see the full error:
   ```bash
   cd ~/my-company/inventory-service
   mvn spotbugs:check
   ```
3. SpotBugs failures are logged but do not stop the agent — the pipeline continues

---

### "dependency-check: command not found" (manual install only)

**Fix:**
1. Verify it is installed: `dependency-check --version`
2. If not found, redo Section 10
3. Make sure the `bin/` directory is in your PATH

---

### "NVD data directory is empty"

The vulnerability database has not been downloaded yet.

**Docker:**

```bash
docker compose run --rm agent \
  dependency-check --updateonly --data /agent-output/nvd-data
```

**Manual install:**

```bash
dependency-check --updateonly --data ~/agent-output/nvd-data
```

---

### Generated tests do not compile

**What to do:**
1. Check `agent-output/reports/llm-errors.log` for LLM output issues
2. Look at the generated test file and fix the compilation error manually
3. Common fixes:
   - Add a missing `import` statement at the top
   - Fix a wrong method name (check the actual method signature in your source)
   - Remove a test method that tests a private method (private methods can't be tested directly)

---

### Docker image build fails at OWASP Dependency-Check download

The Dockerfile downloads the DC zip from GitHub during `docker build`. If your build
machine has no internet access:

1. Download the zip manually: `dependency-check-9.2.0-release.zip` from GitHub releases
2. Copy it into `code-agent/` before building
3. Change the `RUN curl ...` line in the Dockerfile to `COPY dependency-check-9.2.0-release.zip /tmp/dc.zip`

---

### Out of memory during model loading

**Fix:** Switch to a smaller model.

**Docker:** Edit `docker-compose.yml`:

```yaml
- AGENT_LLM_MODEL=codellama:7b-q4
```

**Manual install:** Edit `config/config.yaml`:

```yaml
llm:
  model: "codellama:7b-q4"
```

Then pull: `ollama pull codellama:7b-q4`

---

### The agent ran but I don't see new test files

**Check these things:**
1. Did the run complete successfully? Check logs:
   ```bash
   docker compose logs agent       # Docker
   cat ~/agent-output/reports/run.log  # Manual
   ```
2. Were the coverage targets already met? If your code is already 90%+ covered, no new tests are generated.
3. Did you run with `--dry-run`? Dry-run never writes files. Remove that flag.
4. Check for Ollama errors — if the model timed out, test generation is skipped.

---

## 22. Quick Reference Card

### Docker commands

```bash
# Build the image (run once, or after code changes):
docker compose build

# Run the full pipeline:
docker compose up

# Run and auto-remove the container when done:
docker compose run --rm agent python3 agent/main.py

# Dry-run (no writes):
docker compose run --rm agent python3 agent/main.py --dry-run

# Java only:
docker compose run --rm agent python3 agent/main.py --repo java

# Python only:
docker compose run --rm agent python3 agent/main.py --repo python

# Skip re-indexing (faster):
docker compose run --rm agent python3 agent/main.py --skip-ingest

# Skip security analysis:
docker compose run --rm agent python3 agent/main.py --skip-analysis

# Open a shell inside the container:
docker compose run --rm agent bash

# Follow logs while running:
docker compose logs -f agent

# Start Ollama only (for background scheduling):
docker compose up -d ollama

# Stop everything:
docker compose down
```

### Manual install commands

```bash
# Activate the Python environment:
source ~/unit-test-generator-agent/code-agent/venv/bin/activate  # Linux/macOS
# OR
C:\unit-test-generator-agent\code-agent\venv\Scripts\activate.ps1  # Windows

# Run the agent:
python3 agent/main.py                        # Full run (both Java + Python)
python3 agent/main.py --repo java            # Java only
python3 agent/main.py --repo python          # Python only
python3 agent/main.py --dry-run              # Test run, no files written
python3 agent/main.py --skip-ingest          # Skip re-indexing (faster)
python3 agent/main.py --skip-analysis        # Skip security scans
```

### Override settings without editing config.yaml (manual install)

```bash
AGENT_OUTPUT_BASE=/my/custom/path python3 agent/main.py
AGENT_LLM_MODEL=codellama:13b-q4 python3 agent/main.py
AGENT_OLLAMA_HOST=192.168.1.100 python3 agent/main.py
AGENT_JAVA_REPO=/path/to/other/repo python3 agent/main.py
```

### Check the resolved configuration (manual install)

```bash
python3 agent/config.py     # Prints the full resolved configuration
```

### View the latest report

```bash
# Docker (with bind mount ./agent-output):
xdg-open ./agent-output/reports/*.html

# Manual install on Linux:
xdg-open ~/agent-output/reports/*.html

# Manual install on macOS:
open ~/agent-output/reports/*.html
```

### Check what models are downloaded in Ollama

```bash
# Docker:
docker compose run --rm ollama ollama list

# Manual install:
ollama list
```

### Rebuild ChromaDB from scratch

```bash
# Docker:
docker compose run --rm agent bash -c \
  "rm -rf /agent-output/chromadb && python3 agent/main.py --dry-run --skip-analysis"

# Manual install:
rm -rf ~/agent-output/chromadb
python3 agent/main.py --dry-run --skip-analysis
```

---

*Setup guide for Code-Agent Unit Test Generator. All processing is local — no data leaves your machine.*
