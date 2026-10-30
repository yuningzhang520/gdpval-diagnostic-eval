# Sandbox image for the model under test.
# Build context: docker/sandbox/ only (.dockerignore admits Dockerfile and requirements.txt).
# Nothing from the repository root, data/, private/, plan/ or the harness enters the image.
# Task inputs arrive per sample through Inspect's Sample.files; outputs are collected from
# /output/final/ by the harness. The container runs with network_mode: none.
# python3-uno is Debian's LibreOffice UNO bridge; it is importable from /usr/bin/python3 (the
# distribution interpreter), not from the image's default /usr/local/bin/python3.
FROM python:3.11-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-calc libreoffice-writer libreoffice-impress python3-uno \
        fonts-dejavu fonts-liberation fonts-noto-core \
        poppler-utils unzip zip ca-certificates procps \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN mkdir -p /workspace/inputs /workspace/resources /output/final
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/root \
    SAL_USE_VCLPLUGIN=svp
WORKDIR /workspace
