# MIRA - Microservice Incident Response Agent
# Dockerfile for containerized deployment

# --- Stage 1: Build Python Dependencies ---
FROM python:3.11-slim as python-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install python dependencies
RUN uv pip install --system --no-cache .

# --- Stage 2: Build Azure DevOps MCP (Node.js) ---
FROM node:20-slim as node-builder

WORKDIR /app/azure-devops-mcp

# Copy Azure DevOps MCP source
COPY azure-devops-mcp/ .

# Install dependencies and build
RUN npm install
RUN npm run build
# Prune dev dependencies for production
RUN npm prune --production

# --- Stage 3: Production Image ---
FROM python:3.11-slim as production

WORKDIR /app

# Install Node.js runtime (required for Azure DevOps MCP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from python-builder
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# Copy built Azure DevOps MCP from node-builder
COPY --from=node-builder /app/azure-devops-mcp /app/azure-devops-mcp

# Copy application code
COPY src/ src/
COPY config/ config/

# Create non-root user
RUN useradd -m -u 1000 mira && chown -R mira:mira /app
USER mira

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "mira.dispatcher.main:app", "--host", "0.0.0.0", "--port", "8000"]
