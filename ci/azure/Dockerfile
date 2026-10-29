FROM node:22.16.0-bookworm-slim AS node
FROM docker:27.5.1-cli AS dockercli
FROM python:3.11.14-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

# Only a committed, public Git bundle is uploaded; no .env, databases or local runtime.
ARG EXPECTED_SHA
COPY source.bundle /source.bundle
RUN git clone /source.bundle /theogen-electoral \
    && git -C /theogen-electoral checkout --detach "$EXPECTED_SHA" \
    && test "$(git -C /theogen-electoral rev-parse HEAD)" = "$EXPECTED_SHA" \
    && rm /source.bundle
WORKDIR /theogen-electoral
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 setuptools==84.2.1 \
    && python -m pip install --no-cache-dir -r backend/requirements.txt pip-audit==2.10.1
RUN cd frontend && npm ci && npx playwright install --with-deps chromium
ENTRYPOINT ["python", "ci/azure/run.py"]
