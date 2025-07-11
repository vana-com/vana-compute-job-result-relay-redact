# Builder stage
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ python3-dev

# Install all dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Copy only production dependencies from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source code and config
COPY src/ /app/
COPY config/ /app/config/

# Create directories
RUN mkdir -p /mnt/input /mnt/output

# Set environment variables
ENV PYTHONPATH=/app
ENV DEV_MODE=0
ENV INPUT_PATH=/mnt/input
ENV OUTPUT_PATH=/mnt/output
ENV PRESIDIO_CONFIG_PATH=/app/config/presidio_config.json

CMD ["python", "/app/worker.py"]
