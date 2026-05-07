FROM python:3.11-slim

# System deps for curl (healthcheck) only — no build-essential needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install PyTorch CPU-only FIRST (before other deps) ──────────────────
# This prevents pip from pulling the massive CUDA/GPU torch (~900MB).
# CPU-only torch is ~200MB and sufficient for sentence-transformers inference.
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

# ── Install remaining Python dependencies ────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Ensure openclaw-sdk is installed ─────────────────────────────────────
RUN pip install --no-cache-dir "openclaw-sdk>=2.1.0"

# ── Pre-download the HuggingFace embedding model ─────────────────────────
# Baked into the image so first pipeline run is instant.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Copy application code ─────────────────────────────────────────────────
COPY . .

# Create data/logs directories
RUN mkdir -p data logs

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
