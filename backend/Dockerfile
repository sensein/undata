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

# Create venv and install Python dependencies using uv
COPY pyproject.toml .
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv -e ".[dev]"

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic.ini ./alembic.ini
COPY pytest.ini ./pytest.ini
COPY entrypoint.sh ./entrypoint.sh

# Bundle QUDT vocabulary for unit resolution
COPY data/ ./data/

RUN chmod +x entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["./entrypoint.sh"]
