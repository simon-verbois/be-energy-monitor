# Belgian Energy Monitor — Dockerfile
#
# Uses python:3.11-slim (Debian/glibc) rather than Alpine so that
# pre-built binary wheels for matplotlib, lxml, and pdfplumber install
# cleanly without needing a C toolchain inside the image.

FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# libxml2  — required by lxml (BeautifulSoup4 HTML parser)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# Create the data directory as a fallback (will be overridden by bind mount)
RUN mkdir -p /data

# ── Runtime configuration ─────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    # Prevent "cannot connect to X server" in headless container
    MPLBACKEND=Agg \
    TZ=Europe/Brussels

# ── Entry point ───────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
