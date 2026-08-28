FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr, which
# would delay/garble MCP protocol traffic on stdout and log lines on stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first, in their own layer, for build caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Non-root runtime user. No GCP credentials -- and certainly no service
# account key file -- are ever copied into the image; they must be
# supplied at container runtime via a mounted gcloud ADC file, environment
# variables, or (preferably, when running on GCP) attached workload
# identity/an attached service account.
RUN groupadd --system gcp-network-mcp \
    && useradd --system --gid gcp-network-mcp --create-home gcp-network-mcp
USER gcp-network-mcp

ENTRYPOINT ["gcp-network-mcp"]
