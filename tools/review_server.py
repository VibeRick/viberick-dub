"""Serve the local studio with byte-range media seeking, without a generation API.

uv run uvicorn tools.review_server:app --host 127.0.0.1 --port 8878
Open /?review=./review/manifest.json after preparing an explicit local fixture.
"""
from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "web", html=True))
