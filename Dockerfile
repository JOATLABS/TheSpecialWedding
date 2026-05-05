FROM python:3.11-slim-bookworm

WORKDIR /app

# Apply latest OS security fixes in base image
RUN apt-get update && apt-get -y upgrade && apt-get -y autoremove && rm -rf /var/lib/apt/lists/*

# MongoDB database tools (mongodump/mongorestore for /admin/backup/trigger).
# Pinned .deb from MongoDB CDN — not available in default Debian repos.
# TARGETARCH is set automatically by BuildKit; default to amd64 for legacy
# `docker build` invocations without buildx.
ARG TARGETARCH
ARG MONGODB_TOOLS_VERSION=100.10.0
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) MDB_ARCH=x86_64 ;; \
        arm64) MDB_ARCH=arm64 ;; \
        *) echo "Unsupported TARGETARCH for mongodb-database-tools: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL -o /tmp/mdb-tools.deb \
      "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-${MDB_ARCH}-${MONGODB_TOOLS_VERSION}.deb" && \
    apt-get install -y --no-install-recommends /tmp/mdb-tools.deb && \
    rm /tmp/mdb-tools.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

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
