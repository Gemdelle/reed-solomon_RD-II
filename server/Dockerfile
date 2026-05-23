FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

# Compile every module to optimised bytecode (level 2: no docstrings, no asserts),
# then delete the .py source files so the image ships only the .pyc in __pycache__.
# Python's import system resolves modules from __pycache__ when no .py is present.
RUN python -m compileall -q -o 2 ./src/ && \
    find ./src -name "*.py" -delete

RUN useradd -m appuser && chown -R appuser /app
USER appuser
ENV PYTHONPATH=/app/src
# PYTHONOPTIMIZE=2 must match the -o 2 used in compileall above.
# Python resolves *.opt-2.pyc only when running at optimization level 2;
# without this, it looks for *.pyc (level 0) and fails to import.
ENV PYTHONOPTIMIZE=2
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
