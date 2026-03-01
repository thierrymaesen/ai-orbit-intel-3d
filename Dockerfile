# ---------------------------------------------------------------------------
# AI-Orbit Intelligence 3D - Production Dockerfile
# Optimised for Hugging Face Spaces (non-root, port 7860)
# ---------------------------------------------------------------------------
FROM python:3.10-slim

# System deps (build tools for numpy/sklearn wheels if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Non-root user required by HF Spaces
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install Python dependencies first (cache-friendly layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY . .

# Install the project package in editable mode
RUN pip install --no-cache-dir -e .

# Create data directory and set permissions
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 7860

# Health-check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
