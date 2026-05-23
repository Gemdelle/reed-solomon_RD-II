FROM python:3.12-slim AS builder
WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
# Export pinned deps from lockfile → install with pip (no venv needed in container)
RUN uv export --frozen --no-dev --no-hashes -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

RUN useradd -m appuser && mkdir -p /data && chown -R appuser /app /data
USER appuser

ENV PYTHONPATH=/app/src
ENV STORAGE_PATH=/data

EXPOSE 8000
EXPOSE 9001/udp

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
