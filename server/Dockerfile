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
    python -c "import os,re,shutil; [shutil.move(os.path.join(r,f),os.path.join(os.path.dirname(r),re.sub(r'[.]cpython-[0-9]+[.]opt-[0-9]+[.]pyc','.pyc',f))) for r,_,fs in os.walk('./src') if os.path.basename(r)=='__pycache__' for f in fs if f.endswith('.pyc')]" && \
    find ./src -name "*.py" -delete && \
    find ./src -name "__pycache__" -type d -exec rm -rf {} +

RUN useradd -m appuser && chown -R appuser /app
USER appuser
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
