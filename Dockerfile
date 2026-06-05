# Stage 1: Build virtual environment
FROM python:3.14-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation and optimize cache filesystem operations
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install the project's dependencies independently from source files
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Final runtime image
FROM python:3.14-slim

WORKDIR /app

# Create application directories
RUN mkdir -p /app/data /tmp/s-bridge/pre_collation /tmp/s-bridge/post_collation

# Copy the built virtual environment directly
COPY --from=builder /app/.venv /app/.venv

# Copy all source files in a single layer (Assumes a configured .dockerignore file)
COPY . .

# Place virtual environment executables at the beginning of PATH
ENV PATH="/app/.venv/bin:$PATH"

# Production environment variables
ENV ENVIRONMENT=PROD
ENV NLP_ANALYSIS_DIR=/tmp/s-bridge/pre_collation
ENV COLLATION_DIR=/tmp/s-bridge/post_collation
ENV DATA_DIR=/app/data

EXPOSE 8500

ENTRYPOINT ["/app/entrypoint.sh"]

#To construct the docker, run "docker build -t s-bridge:latest ."
#Once built, run "docker run -p 8500:8500 s-bridge:latest"