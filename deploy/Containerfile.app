FROM docker.io/library/python:3.13-slim AS builder

# Copy UV runtime binaries from the upstream image so we can run `uv sync`
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt/scarab

# Project metadata for creating a frozen .venv using UV
COPY pyproject.toml uv.lock /opt/scarab/
COPY src /opt/scarab/src

# Install project dependencies into an isolated virtualenv (.venv)
ENV PATH="/opt/scarab/.venv/bin:$PATH"
RUN uv sync --frozen --no-dev

FROM docker.io/library/python:3.13-slim AS final

# Create a non-root system user `scarab` and use /opt/scarab as working directory.
RUN groupadd --system scarab \
    && useradd --system --gid scarab --home /opt/scarab --no-create-home --shell /usr/sbin/nologin scarab

WORKDIR /opt/scarab

# Copy the virtualenv and application code from the builder.
COPY --from=builder /opt/scarab/.venv /opt/scarab/.venv
COPY --from=builder /opt/scarab/src /opt/scarab/src

# Give the non-root user ownership of the immutable application tree.
RUN chown -R scarab:scarab /opt/scarab

ENV PATH="/opt/scarab/.venv/bin:$PATH"

# Run as non-root user
USER scarab

# Entrypoint: runtime configuration is mounted read-only from the host.
CMD ["python", "-m", "src.main", "/etc/scarab"]
