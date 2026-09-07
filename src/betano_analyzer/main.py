from datetime import date

from fastapi import FastAPI

from .api import router
from .db import initialize
from .web import dashboard_response

# Initialize the local schema at import time as well as on FastAPI startup.
# This keeps direct TestClient usage and CLI/module imports deterministic.
initialize()

app = FastAPI(title="Betano Live Analyzer", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    initialize()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "betano-live-analyzer"}


@app.get("/", include_in_schema=False)
def dashboard():
    return dashboard_response(date.today())
