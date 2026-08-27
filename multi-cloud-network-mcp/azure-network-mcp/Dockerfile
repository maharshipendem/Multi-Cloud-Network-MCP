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

# Non-root runtime user. No Azure credentials are ever copied into the
# image; they must be supplied at container runtime via environment
# variables, a mounted Azure CLI config directory, or (preferably, when
# running in Azure) an attached managed identity.
RUN groupadd --system azure-network-mcp \
    && useradd --system --gid azure-network-mcp --create-home azure-network-mcp
USER azure-network-mcp

ENTRYPOINT ["azure-network-mcp"]
