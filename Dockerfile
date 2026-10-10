# One image for both the API service and the worker job.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy DUB_IN_CONTAINER=1 DUB_RUNS=/tmp/runs PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group sep --no-install-project
# Bake the demucs model weights into the image so a job does not download them.
RUN uv run --no-sync python -c "from demucs.pretrained import get_model; get_model('htdemucs')"
COPY dub ./dub
COPY server ./server
ENV PATH="/app/.venv/bin:$PATH"
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
