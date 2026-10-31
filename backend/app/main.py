"""PromoLens API. Run from backend/: uvicorn app.main:app --reload"""

from __future__ import annotations

import os
from pathlib import Path

import pyexasol
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers.api import router

app = FastAPI(title="PromoLens", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router)


def _error(status: int, error: str, hint: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "hint": hint})


@app.exception_handler(KeyError)
async def key_error(_: Request, exc: KeyError) -> JSONResponse:
    return _error(404, str(exc.args[0]) if exc.args else "Not found", "Check the dataset, group or metric name.")


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError) -> JSONResponse:
    return _error(422, str(exc), "Adjust the inputs and try again.")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []))
    return _error(422, f"Invalid input {where}: {first.get('msg', 'invalid value')}", "Adjust the inputs and try again.")


@app.exception_handler(RuntimeError)
async def runtime_error(_: Request, exc: RuntimeError) -> JSONResponse:
    return _error(503, str(exc), "Check .env at the repo root, then run python -m pipeline.doctor from backend/.")


@app.exception_handler(pyexasol.ExaError)
async def exa_error(_: Request, exc: pyexasol.ExaError) -> JSONResponse:
    msg = str(exc)
    if "not found" in msg.lower() or "object" in msg.lower() and "does not exist" in msg.lower():
        return _error(503, "This dataset has not been processed yet.", "Run python -m pipeline.all --dataset <id> from backend/.")
    if isinstance(exc, pyexasol.ExaCommunicationError | pyexasol.ExaConnectionError):
        return _error(503, "Exasol is not reachable.", "Start the exasoldb container (docker ps), then retry.")
    return _error(500, "An Exasol query failed.", "See the backend log for the SQL error; run python -m pipeline.doctor.")


# Single-process deployment: when the frontend has been built (npm run build), serve it from the API.
_DIST = Path(os.environ.get("PROMOLENS_STATIC", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if (_DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise KeyError("No such API route")
        target = (_DIST / path).resolve()
        if path and target.is_file() and _DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")
