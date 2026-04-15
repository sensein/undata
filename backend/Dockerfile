FROM python:3.14-slim

WORKDIR /app

# Install system deps for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create venv
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Install library first (editable)
COPY library/ /app/library/
RUN uv pip install -e /app/library

# Install backend
COPY backend/pyproject.toml /app/backend/
RUN uv pip install -e "/app/backend[dev]"

# Copy source
COPY backend/src /app/backend/src
COPY backend/seed /app/backend/seed
COPY backend/entrypoint.sh /app/backend/

WORKDIR /app/backend
EXPOSE 8002
ENTRYPOINT ["./entrypoint.sh"]
