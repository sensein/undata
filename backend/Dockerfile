FROM python:3.14-slim

WORKDIR /app

# Install system dependencies for asyncpg and pgvector
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx

# Copy and install undata-library (backend depends on it)
COPY library/ /library/
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv -e /library

# Install backend Python dependencies
COPY backend/pyproject.toml .
RUN uv pip install --python /app/.venv -e ".[dev]"

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

COPY backend/src/ ./src/
COPY backend/tests/ ./tests/
COPY backend/alembic.ini ./alembic.ini
COPY backend/pytest.ini ./pytest.ini
COPY backend/entrypoint.sh ./entrypoint.sh

# Bundle QUDT vocabulary for unit resolution
COPY backend/data/ ./data/

RUN chmod +x entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["./entrypoint.sh"]
