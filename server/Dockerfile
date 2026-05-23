FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

# Compile to optimised bytecode (level 2: strips docstrings + assert statements),
# then promote each __pycache__/module.cpython-XY.opt-2.pyc → module.pyc in the
# parent directory. SourcelessFileLoader looks for "module.pyc" directly in the
# module search path — it does NOT scan __pycache__ when no .py anchor is present.
RUN python -m compileall -q -o 2 ./src/ && \
    python -c "
import os, re, shutil
for root, _, files in os.walk('./src'):
    if os.path.basename(root) == '__pycache__':
        parent = os.path.dirname(root)
        for f in files:
            if f.endswith('.pyc'):
                simple = re.sub(r'\.cpython-\d+\.opt-\d+\.pyc$', '.pyc', f)
                shutil.move(os.path.join(root, f), os.path.join(parent, simple))
" && \
    find ./src -name "*.py" -delete && \
    find ./src -name "__pycache__" -type d -exec rm -rf {} +

RUN useradd -m appuser && chown -R appuser /app
USER appuser
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
