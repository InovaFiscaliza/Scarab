FROM docker.io/library/python:3.13-slim AS builder

# Copy UV runtime binaries from the upstream image so we can run `uv sync`
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Project metadata for creating a frozen .venv using UV
COPY pyproject.toml uv.lock /app/
COPY src /app/src

# Install project dependencies into an isolated virtualenv (.venv)
ENV PATH="/app/.venv/bin:$PATH"
RUN uv sync --frozen --no-dev

# Copy application configuration into the builder stage so it can be
# transferred into the final, minimal runtime image.
COPY config /app/config

FROM docker.io/library/python:3.13-slim AS final

# Create a non-root system user `scarab` and use /app as working directory.
RUN groupadd --system scarab \
    && useradd --system --gid scarab --home /app --no-create-home --shell /usr/sbin/nologin scarab

WORKDIR /app

# Copy the virtualenv, application code and configuration from the builder.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/config /app/config

# Give the non-root user ownership of /app
RUN chown -R scarab:scarab /app

ENV PATH="/app/.venv/bin:$PATH"

# Run as non-root user
USER scarab

# Entrypoint: `src.main` expects a single argument: path to the config directory
CMD ["python", "-m", "src.main", "/app/config"]
