FROM python:3.12-slim AS builder

WORKDIR /app
# Build deps for any C-extension wheels (most modern wheels are pre-built,
# but keep it conservative for cffi/Pillow-style fallbacks).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim

WORKDIR /app
# Runtime deps for WeasyPrint (Cairo / Pango / GDK / fontconfig).
# Without these the import succeeds but PDF rendering fails at runtime
# with cryptic "no module named cairo" or font-fallback errors.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi8 shared-mime-info fonts-dejavu \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
