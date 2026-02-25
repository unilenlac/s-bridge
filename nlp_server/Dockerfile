FROM python:3.14-slim

WORKDIR /app

# System dependencies for cltk/stanza
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install specific Python packages
RUN pip install --no-cache-dir fastapi uvicorn cltk[stanza]>=2.5.0

# Pre-download models to avoid downloading on every container start
# We write a tiny python script to trigger the stanza grc download
RUN python -c "from cltk import NLP; nlp = NLP('grc', backend='stanza', suppress_banner=True)"

# Copy server code
COPY main.py /app/main.py

EXPOSE 8000

# Run Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
