# Complete Setup Guide — Code-Agent Unit Test Generator

> **Who is this guide for?**
> This guide is written for anyone — even if you have never set up a software project before.
> Every step is explained in plain language. Follow the steps in order and you will have the
> agent running by the end.

---

## Table of Contents

1. [What Does This Software Do?](#1-what-does-this-software-do)
2. [What Does Your Computer Need?](#2-what-does-your-computer-need)
3. [Choose Your Platform](#3-choose-your-platform)
4. [Install Java (JDK 17)](#4-install-java-jdk-17)
5. [Install Maven](#5-install-maven)
6. [Install Python 3.11](#6-install-python-311)
7. [Install Git](#7-install-git)
8. [Install Ollama (The AI Brain)](#8-install-ollama-the-ai-brain)
9. [Install dependency-check (Security Scanner)](#9-install-dependency-check-security-scanner)
10. [Install Semgrep (Code Pattern Scanner)](#10-install-semgrep-code-pattern-scanner)
11. [Download This Project](#11-download-this-project)
12. [Run the Setup Script](#12-run-the-setup-script)
13. [Tell the Agent Where Your Code Is](#13-tell-the-agent-where-your-code-is)
14. [Prepare Your Java Project (pom.xml Changes)](#14-prepare-your-java-project-pomxml-changes)
15. [Build the RAG Knowledge Base (ChromaDB)](#15-build-the-rag-knowledge-base-chromadb)
16. [Run Your First Dry-Run](#16-run-your-first-dry-run)
17. [Run the Full Pipeline](#17-run-the-full-pipeline)
18. [Understanding the Output and Reports](#18-understanding-the-output-and-reports)
19. [Schedule Automatic Weekly Runs](#19-schedule-automatic-weekly-runs)
20. [Troubleshooting Common Problems](#20-troubleshooting-common-problems)
21. [Quick Reference Card](#21-quick-reference-card)

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

The agent works on all of these — pick your platform:

- **Linux** (Ubuntu 20.04+ or similar) — recommended
- **macOS** (12 Monterey or later)
- **Windows with WSL2** — run Linux inside Windows (recommended for Windows users)
- **Windows Native** — run directly without WSL2

---

## 3. Choose Your Platform

### Windows Users — Which Should You Pick?

**Option A: WSL2 (Recommended for Windows)**
WSL2 gives you a full Linux environment inside Windows. Most things work better this way.
Use this if you have Windows 10 (version 2004+) or Windows 11.

**Option B: Windows Native**
Run everything directly in PowerShell. Simpler setup but some tools have less support.

To check your Windows version: press `Win + R`, type `winver`, press Enter.

### How to Install WSL2 (Windows users, Option A only)

1. Open **PowerShell as Administrator** (right-click PowerShell → "Run as administrator")
2. Type this command and press Enter:
   ```powershell
   wsl --install
   ```
3. Restart your computer when prompted
4. After restart, Ubuntu will open automatically — set a username and password
5. You now have a Linux terminal inside Windows

> From this point, **WSL2 users follow the Linux instructions** in each section below.
> Open Ubuntu from the Start menu whenever you need a terminal.

---

## 4. Install Java (JDK 17)

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

## 5. Install Maven

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

## 6. Install Python 3.11

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

## 7. Install Git

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

## 8. Install Ollama (The AI Brain)

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

## 9. Install dependency-check (Security Scanner)

This tool scans your Java project for known security vulnerabilities in libraries.

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

## 10. Install Semgrep (Code Pattern Scanner)

Semgrep scans your code for security patterns.

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

## 11. Download This Project

### Option A: Using Git (recommended)

```bash
git clone <repository-url> code-agent
cd code-agent
```

> Replace `<repository-url>` with the actual URL of this repository.

### Option B: Download as ZIP

1. Download the ZIP file from the repository
2. Extract it to a folder, e.g., `~/code-agent` (Linux/Mac) or `C:\code-agent` (Windows)
3. Open a terminal and navigate to that folder:
   ```bash
   cd ~/code-agent        # Linux/macOS
   cd C:\code-agent       # Windows PowerShell
   ```

---

## 12. Run the Setup Script

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

## 13. Tell the Agent Where Your Code Is

This is the most important configuration step. Open the file `config/config.yaml`
in any text editor (Notepad, VS Code, nano, etc.).

Find the `repos` section near the top of the file:

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

You can run the agent for Java only. Just set a dummy path for Python that does not exist:

```yaml
repos:
  java_repo_path:   "~/my-company/inventory-service"
  python_repo_path: "~/does-not-exist"
```

Then run the agent with `--repo java` (explained in Step 17).

### Other settings you may want to change

You usually do **not** need to change anything else, but here are the key settings if needed:

```yaml
output:
  base_dir: "~/agent-output"        # Where reports and tests are saved
                                    # Change this if you want a different location

llm:
  base_url: "auto"                  # Leave as "auto" — the agent detects Ollama automatically
  model: "codellama:7b-q4"         # Set by setup script — don't change manually

coverage:
  target_pct: 90                    # Stop generating tests when 90% of code is covered
  max_iterations: 3                 # Try up to 3 rounds of test generation per run
```

---

## 14. Prepare Your Java Project (pom.xml Changes)

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

### Where to put these plugins in pom.xml

Your `pom.xml` should look like this (simplified):

```xml
<project>
  ...
  <build>
    <plugins>

      <!-- your existing plugins here -->

      <!-- ADD THESE THREE BLOCKS: -->

      <!-- JaCoCo -->
      <plugin>
        <groupId>org.jacoco</groupId>
        ...
      </plugin>

      <!-- SpotBugs -->
      <plugin>
        <groupId>com.github.spotbugs</groupId>
        ...
      </plugin>

      <!-- build-helper -->
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        ...
      </plugin>

    </plugins>
  </build>
  ...
</project>
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

## 15. Build the RAG Knowledge Base (ChromaDB)

RAG stands for **Retrieval-Augmented Generation**. Think of it as giving the AI a
"library card" — before generating tests, the AI searches a local database of your code
to understand context (what classes exist, how methods call each other, etc.).

This database is called **ChromaDB** and it lives on your computer in `~/agent-output/chromadb/`.

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
extra to do — just run the agent (Step 17) and the database will be built.

However, if you want to build *only* the database without running the full pipeline
(e.g., to verify it works), you can do so:

```bash
source venv/bin/activate          # Linux/macOS
# OR
venv\Scripts\activate.ps1         # Windows PowerShell

python3 agent/main.py --dry-run --skip-analysis
```

This will:
- Build the ChromaDB database from your code
- Show you statistics (how many chunks were indexed)
- Not generate any tests or reports

### What gets indexed

| Language | What is indexed |
| --- | --- |
| Java | All `.java` files (except files in `test/` folders) |
| Python | All `.py` files (except files in `tests/` folders) |

The indexer automatically skips your existing test files so it only learns from your
production code.

### How the database stays up-to-date

On every subsequent run, the agent only re-indexes files that **changed since the last run**
(detected via `git diff`). This makes it fast on subsequent runs.

### Checking the database was built

After the first run, you should see:

```
~/agent-output/chromadb/
├── chroma.sqlite3          ← Main database file
└── ... (other ChromaDB files)
```

---

## 16. Run Your First Dry-Run

A **dry-run** does everything except actually write test files or reports. Use it to
verify that the agent can connect to all the tools and read your code.

```bash
# Linux / macOS / WSL2:
cd ~/code-agent                     # Navigate to the project folder
source venv/bin/activate            # Activate the Python environment
python3 agent/main.py --dry-run

# Windows Native (PowerShell):
cd C:\code-agent
venv\Scripts\activate.ps1
python agent\main.py --dry-run
```

### What a successful dry-run looks like

You will see output like this (simplified):

```
[INFO]  Loading configuration...
[INFO]  Platform: linux (or macos / windows_wsl2)
[INFO]  Ollama reachable at http://localhost:11434
[INFO]  Model: codellama:7b-q4
[INFO]  Java repo: /home/yourname/my-company/inventory-service  ✓ exists
[INFO]  Step 1/9 — Indexing Java repo...
[INFO]    Chunked 127 methods from 34 Java files
[INFO]    Embedded 127 chunks
[INFO]    [dry-run] Would upsert 127 chunks to ChromaDB
[INFO]  Step 2/9 — Running vulnerability analysis...
[INFO]    [dry-run] Would run SpotBugs, OWASP DC, Bandit, Semgrep
[INFO]  ...
[INFO]  Step 9/9 — [dry-run] Would render report to ~/agent-output/reports/2025-W22-report.html
[INFO]  Dry-run complete. No files written.
```

### Common dry-run failures and fixes

**"Repo path does not exist"**
→ Check `config/config.yaml` — the path you entered does not exist on your system.
Check for typos. Use `ls ~/path/to/your/repo` to verify the path.

**"Ollama is not reachable"**
→ Ollama is not running. Start it:
- Linux/macOS: `ollama serve`
- Windows: Open the Ollama app from the Start menu or system tray

**"java: command not found" or "mvn: command not found"**
→ Java or Maven is not installed correctly, or not in your PATH. Redo Steps 4 and 5.

---

## 17. Run the Full Pipeline

Once the dry-run succeeds, run the full pipeline:

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

Total time varies greatly depending on your hardware and code size.

### Running for one language only

```bash
# Java only:
python3 agent/main.py --repo java

# Python only:
python3 agent/main.py --repo python
```

### Skipping the re-indexing (faster subsequent runs)

If your code has not changed, you can skip re-indexing ChromaDB:

```bash
python3 agent/main.py --skip-ingest
```

### Skipping security analysis (test generation only)

```bash
python3 agent/main.py --skip-analysis
```

---

## 18. Understanding the Output and Reports

After a successful run, everything is saved under `~/agent-output/`:

```
~/agent-output/
├── reports/
│   ├── 2025-W22-report.html    ← Main weekly report (open in browser)
│   ├── 2025-W22-report.pdf     ← Same report as PDF
│   ├── run_history.json        ← Tracks coverage over time
│   └── run.log                 ← Log of the last scheduled run
├── generated-tests/
│   ├── java/                   ← Generated JUnit 5 test files
│   │   └── com/example/service/
│   │       └── UserServiceTest.java
│   └── python/                 ← Generated pytest test files
│       └── test_items.py
└── chromadb/                   ← The RAG knowledge database (do not delete)
```

### How to view the report

Open the `.html` file in any web browser (Chrome, Firefox, Edge, Safari).

**On Linux / macOS:**
```bash
xdg-open ~/agent-output/reports/2025-W22-report.html    # Linux
open ~/agent-output/reports/2025-W22-report.html         # macOS
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

### What to do with the generated test files

The generated test files in `~/agent-output/generated-tests/java/` are **suggestions**.
They are written by AI and may not compile perfectly every time. You should:

1. Review them for correctness
2. Fix any compilation errors
3. Move them into your project's test source folder if you want to keep them permanently
4. Or run them directly using the Maven property (see below)

### Running generated tests manually

```bash
# Linux / WSL2:
cd ~/my-company/inventory-service
mvn test jacoco:report -Dagent.tests.dir=$HOME/agent-output/generated-tests/java

# Windows:
cd C:\Users\YourName\my-company\inventory-service
mvn test jacoco:report "-Dagent.tests.dir=C:\Users\YourName\agent-output\generated-tests\java"
```

---

## 19. Schedule Automatic Weekly Runs

The agent is designed to run automatically once a week (Sunday at 2:00 AM by default).
Here is how to set up the schedule.

### Linux / WSL2 — Using cron

The setup script already registered the cron job. To verify:

```bash
crontab -l
```

You should see a line like:
```
0 2 * * 0 /home/yourname/code-agent/scripts/run_agent.sh >> /home/yourname/agent-output/reports/run.log 2>&1
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

WSL2 does not start automatically. Add this to `/etc/wsl.conf` inside WSL2:

```bash
sudo nano /etc/wsl.conf
```

Add these lines:

```ini
[boot]
command=service cron start
```

Save with `Ctrl+O`, exit with `Ctrl+X`. Restart WSL2 for this to take effect.

### macOS — Using cron

```bash
crontab -e
```

Add this line (adjust the path to your actual code-agent location):

```
0 2 * * 0 /Users/yourname/code-agent/scripts/run_agent.sh >> /Users/yourname/agent-output/reports/run.log 2>&1
```

### Windows Native — Using Task Scheduler

Open an elevated PowerShell (right-click → Run as administrator) and run:

```powershell
$Action  = New-ScheduledTaskAction -Execute "pwsh" -Argument "-File `"C:\code-agent\scripts\run_agent.ps1`""
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "CodeAgent" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest
```

Adjust `C:\code-agent` to wherever you installed the project.

### Changing when the agent runs

Edit `config/config.yaml` under the `schedule` section:

```yaml
schedule:
  cron_expression: "0 2 * * 0"
```

Cron format: `minute  hour  day-of-month  month  day-of-week`

Examples:
- `0 2 * * 0` = Sunday 2:00 AM
- `0 8 * * 1` = Monday 8:00 AM
- `0 0 1 * *` = First day of every month at midnight

---

## 20. Troubleshooting Common Problems

### "Ollama is not reachable"

The agent cannot connect to the AI model.

**Fix:**
1. Make sure Ollama is running:
   - Linux/macOS: Run `ollama serve` in a terminal (keep it open)
   - Windows: Open the Ollama app from the Start menu
2. Test the connection:
   ```bash
   curl http://localhost:11434/api/tags
   ```
   If this fails, Ollama is not running.
3. WSL2 users: The Windows host IP is detected automatically. If it seems wrong, override it:
   ```bash
   export AGENT_OLLAMA_HOST=<your-windows-ip>
   python3 agent/main.py --dry-run
   ```
   Find your Windows IP from WSL2: `ip route show default | awk '{print $3}'`

---

### "Repo path does not exist"

The path you entered in `config/config.yaml` does not exist on your system.

**Fix:**
1. Check the path exists:
   ```bash
   ls ~/my-company/inventory-service
   ```
2. If you see "No such file or directory", the path is wrong
3. Find the correct path:
   ```bash
   find ~ -name "pom.xml" 2>/dev/null    # Find Java projects by pom.xml
   ```
4. Update `config/config.yaml` with the correct path

---

### "JaCoCo report not found" or "jacoco.xml is missing"

The agent cannot find the test coverage report for your Java project.

**Fix:**
1. Check that the JaCoCo plugin is in your `pom.xml` (see Step 14)
2. Run Maven manually to generate the report:
   ```bash
   cd ~/my-company/inventory-service
   mvn test jacoco:report
   ```
3. Check that this file was created:
   ```bash
   ls target/site/jacoco/jacoco.xml
   ```
4. If Maven fails, look at the error and fix your code first (the agent requires compilable code)

---

### "Model not found" or "model not loaded"

The AI model is not downloaded in Ollama.

**Fix:** Pull the model manually:
```bash
ollama pull codellama:7b-q4       # CPU model
ollama pull codellama:13b-q4      # GPU 8 GB+ model
ollama pull nomic-embed-text      # Embedding model (always required)
```

List downloaded models: `ollama list`

---

### "SpotBugs: BUILD FAILURE"

Maven SpotBugs scan failed.

**Fix:**
1. Check that SpotBugs plugin is in your `pom.xml` (see Step 14)
2. Run SpotBugs manually to see the error:
   ```bash
   cd ~/my-company/inventory-service
   mvn spotbugs:check
   ```
3. SpotBugs failures are logged but do not stop the agent — the pipeline continues

---

### "dependency-check: command not found"

The OWASP Dependency-Check tool is not installed or not in PATH.

**Fix:**
1. Verify it is installed: `dependency-check --version`
2. If not found, redo Step 9
3. Make sure the `bin/` directory is in your PATH

---

### "NVD data directory is empty"

The vulnerability database has not been downloaded yet.

**Fix:** Run this once (requires internet, ~2 GB download):
```bash
dependency-check --updateonly --data ~/agent-output/nvd-data
```

---

### Generated tests do not compile

The AI sometimes generates test code with small errors.

**What to do:**
1. Check `~/agent-output/reports/llm-errors.log` for LLM output issues
2. Look at the generated test file and fix the compilation error manually
3. Common fixes:
   - Add a missing `import` statement at the top
   - Fix a wrong method name (check the actual method signature in your source)
   - Remove a test method that tests a private method (private methods can't be tested directly)

---

### Out of memory during model loading

The AI model is too large for your system.

**Fix:** Switch to a smaller model:
1. Edit `config/config.yaml`:
   ```yaml
   llm:
     model: "codellama:7b-q4"     # Smallest model, works on CPU with 8 GB RAM
   ```
2. Pull the smaller model: `ollama pull codellama:7b-q4`

---

### "Permission denied" errors on Linux/macOS

**Fix:**
```bash
chmod +x ~/code-agent/scripts/run_agent.sh
chmod +x ~/code-agent/scripts/setup.sh
```

---

### The agent ran but I don't see new test files

**Check these things:**
1. Did the run complete successfully? Check the log:
   ```bash
   cat ~/agent-output/reports/run.log
   ```
2. Were the coverage targets already met? If your code is already 90%+ covered, no new tests are generated.
3. Did you run with `--dry-run`? Dry-run never writes files. Remove that flag.
4. Check for Ollama errors — if the model timed out, test generation is skipped.

---

## 21. Quick Reference Card

### Activate the Python environment

```bash
# Linux/macOS/WSL2:
source ~/code-agent/venv/bin/activate

# Windows:
C:\code-agent\venv\Scripts\activate.ps1
```

### Run the agent

```bash
python3 agent/main.py                        # Full run (both Java + Python)
python3 agent/main.py --repo java            # Java only
python3 agent/main.py --repo python          # Python only
python3 agent/main.py --dry-run             # Test run, no files written
python3 agent/main.py --skip-ingest         # Skip re-indexing (faster)
python3 agent/main.py --skip-analysis       # Skip security scans
```

### Override settings without editing config.yaml

```bash
# Change the output folder:
AGENT_OUTPUT_BASE=/my/custom/path python3 agent/main.py

# Use a different AI model:
AGENT_LLM_MODEL=codellama:13b-q4 python3 agent/main.py

# Manually set the Ollama host:
AGENT_OLLAMA_HOST=192.168.1.100 python3 agent/main.py

# Point to a different Java repo:
AGENT_JAVA_REPO=/path/to/other/repo python3 agent/main.py
```

### Check if everything is connected

```bash
python3 agent/config.py     # Prints the full resolved configuration
```

### View the latest report

```bash
ls ~/agent-output/reports/                   # List all reports
# Open the latest:
xdg-open ~/agent-output/reports/*.html       # Linux
open ~/agent-output/reports/*.html           # macOS
```

### Check what models are downloaded in Ollama

```bash
ollama list
```

### Rebuild ChromaDB from scratch

```bash
rm -rf ~/agent-output/chromadb               # Delete existing database
python3 agent/main.py --dry-run --skip-analysis   # Rebuild only (dry-run)
```

---

*Setup guide for Code-Agent Unit Test Generator. All processing is local — no data leaves your machine.*
