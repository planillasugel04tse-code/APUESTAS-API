from fastapi import FastAPI

from .api import router
from .db import initialize

app = FastAPI(title="Betano Live Analyzer", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    initialize()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "betano-live-analyzer"}
