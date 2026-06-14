# Production image for the AI Multi-Agent Content Pipeline.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OUTPUT_DIR=/tmp/output

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY app ./app
COPY server.py run.py ./

# The platform injects $PORT; server.py reads it. Expose for local docker run.
EXPOSE 8000

CMD ["python", "server.py"]
