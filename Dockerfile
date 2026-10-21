FROM python:3.14-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project

COPY api ./api

EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
