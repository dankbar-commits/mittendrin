FROM python:3.12-slim

# uv, pulled straight from its official image rather than pip-installed
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependency files first so `uv sync` is cached unless these change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

# 0.0.0.0, not localhost — otherwise the app is unreachable from outside
# the container even though it "works" if you exec into it
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
