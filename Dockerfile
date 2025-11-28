# -------------------------------
# Stage 1: Builder (installs uv and dependencies)
# -------------------------------
FROM python:3.12-slim AS builder

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (Rust-based ultra-fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (creates .venv)
RUN uv sync --frozen

# Copy source
COPY . .

# -------------------------------
# Stage 2: Final runtime
# -------------------------------
FROM python:3.12-slim AS runner

ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Install uv again (small install, needed to activate venv)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy virtual environment + source from builder
COPY --from=builder /app /app

# Expose default port (if FastAPI, Flask etc)
EXPOSE 8010

# Default command (FastAPI example)
# Change this according to your application
# CMD ["uv", "run", "uvicorn", "app.main:app", "--reload"]
CMD ["uvicorn", "run", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
