FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["/entrypoint.sh"]
