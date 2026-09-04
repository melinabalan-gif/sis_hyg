# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG PYTHON_IMAGE=python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.9@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /opt/hys-api

COPY --from=uv /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
RUN uv sync --frozen --no-dev

FROM ${PYTHON_IMAGE} AS runtime

ENV PATH="/opt/hys-api/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 hys \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/hys hys

WORKDIR /opt/hys-api
COPY --from=builder --chown=hys:hys /opt/hys-api /opt/hys-api

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2).read()"]

CMD ["uvicorn", "hys_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
