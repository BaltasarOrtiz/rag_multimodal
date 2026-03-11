FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para pypdf, pillow y pymupdf
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crea directorios necesarios y configura usuario no-root
RUN mkdir -p /app/data /app/storage /home/appuser /tmp/fastembed_cache \
    && addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /home/appuser appuser \
    && chown -R appuser:appgroup /app /home/appuser /tmp/fastembed_cache

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
