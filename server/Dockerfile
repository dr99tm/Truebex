# The Truebex API image (PF14): uvicorn for the `api` service and
# `python -m app.worker` for the `worker` service (infra/host/compose.yaml).
#
#   docker build -t truebex-api server/

# --- rust-minidump's stackwalker (MIT / Apache-2.0), for crash symbolication
FROM rust:1-slim-bookworm AS stackwalk
ARG MINIDUMP_STACKWALK_VERSION=0.27.0
RUN cargo install minidump-stackwalk --locked --version ${MINIDUMP_STACKWALK_VERSION} --root /opt/stackwalk

# --- the API
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system --gid 10001 truebex \
    && useradd --system --uid 10001 --gid truebex --home-dir /app --no-create-home truebex
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --from=stackwalk /opt/stackwalk/bin/minidump-stackwalk /usr/local/bin/minidump-stackwalk
COPY app ./app
COPY scripts ./scripts
USER truebex
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "2"]
