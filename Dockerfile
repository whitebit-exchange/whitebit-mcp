FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /bin/

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-install-project --no-dev

FROM python:3.13-slim

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY server.py .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "server.py"]
