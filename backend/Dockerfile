# ── Stage 1: builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Dependencias del sistema necesarias para compilar paquetes
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime mínimo ──────────────────────────────────
FROM python:3.11-slim AS final

# Dependencias de runtime (sin gcc)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

# Solo los archivos estrictamente necesarios para producción
COPY main.py config.py logger.py ./
COPY rag/ ./rag/

# Crea directorios necesarios y configura usuario no-root
RUN mkdir -p /app/data /app/storage /home/appuser /tmp/fastembed_cache \
    && addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /home/appuser appuser \
    && chown -R appuser:appgroup /app /home/appuser /tmp/fastembed_cache

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
