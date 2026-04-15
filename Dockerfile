FROM python:3.11-slim-bookworm

WORKDIR /app

# Apply latest OS security fixes in base image
RUN apt-get update && apt-get -y upgrade && apt-get -y autoremove && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy entire app and scripts
COPY ./app ./app
COPY ./scripts ./scripts

# Run admin setup script via entrypoint (env-driven, optional)
ENV PYTHONUNBUFFERED=1

# Run as non-root for better security posture
RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "python scripts/bootstrap_runtime.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Expose the port the app runs on
EXPOSE 8000
