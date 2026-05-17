"""FastAPI service exposing the ask() pipeline for the Next.js UI.

The Python side stays the source of truth. The UI is a thin presentation
layer over this API.

Run:
    uv run uvicorn src.api.server:app --reload --port 8000
"""
