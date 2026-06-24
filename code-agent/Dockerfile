FROM python:3.11-slim

# Install system packages:
#   - OpenJDK 17 + Maven  (SpotBugs runs via `mvn spotbugs:check`)
#   - WeasyPrint deps      (cairo/pango for HTML→PDF rendering)
#   - Build tools          (C extensions in pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless \
    maven \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    pkg-config \
    gcc \
    g++ \
    git \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# OWASP Dependency-Check CLI
ARG DC_VERSION=9.2.0
RUN curl -fsSL \
    "https://github.com/jeremylong/DependencyCheck/releases/download/v${DC_VERSION}/dependency-check-${DC_VERSION}-release.zip" \
    -o /tmp/dc.zip \
    && unzip -q /tmp/dc.zip -d /opt/ \
    && chmod +x /opt/dependency-check/bin/dependency-check.sh \
    && ln -s /opt/dependency-check/bin/dependency-check.sh /usr/local/bin/dependency-check \
    && rm /tmp/dc.zip

WORKDIR /app

# Install Python deps as a separate layer so rebuilds are fast
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy agent source code
COPY . .

# Pre-create output directory tree (volume mount will overlay these at runtime)
RUN mkdir -p \
    /agent-output/chromadb \
    /agent-output/reports \
    /agent-output/generated-tests/java \
    /agent-output/generated-tests/python \
    /agent-output/semgrep-rules \
    /agent-output/nvd-data \
    /agent-output/dc-report

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV AGENT_OUTPUT_BASE=/agent-output
ENV AGENT_PLATFORM=linux

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "agent/main.py"]
