FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Create venv and install deps
RUN uv venv .venv && \
    uv pip install --python .venv/bin/python -e ".[dev]"

# Copy source code
COPY src/ ./src/
COPY tests/ ./tests/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
