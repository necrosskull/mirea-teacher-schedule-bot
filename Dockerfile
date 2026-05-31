FROM python:3.14-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/usr/local

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

RUN mkdir -p /app/bot/db/data

COPY . .

CMD ["uv", "run", "python", "-m", "bot"]
