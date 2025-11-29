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
# This step replaces 'pip install -r requirements.txt'
RUN uv sync --frozen

# Copy source
COPY . .

# -------------------------------
# Stage 2: Final runtime
# -------------------------------
FROM python:3.12-slim AS runner

# Set PATH to include uv's install location and ensure Python output is unbuffered
ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Install uv again (small install, needed for the final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy virtual environment + source from builder
# The .venv directory created by 'uv sync' in the builder stage is copied here
COPY --from=builder /app /app

# Expose default port (if FastAPI, Flask etc)
EXPOSE 8010

# Default command (FastAPI example)
# The dependencies (like uvicorn) are already installed via uv
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
# ... (Runner Stage continues) ...

# Default command using 'uv run'
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]