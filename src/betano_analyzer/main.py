from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI

from .api import router
from .arbitrage_api import router as arbitrage_router
from .bookmakers_api import router as bookmakers_router
from .bookmakers_panel import bookmakers_panel_page
from .control_panel import control_panel_page
from .db import initialize
from .health_api import router as health_router
from .model_api import router as model_router
from .oddspapi_api import router as oddspapi_router
from .provider_accounts_api import router as provider_accounts_router
from .provider_accounts_panel import provider_accounts_page
from .telegram_api import router as telegram_router
from .telegram_test_web import telegram_test_page
from .web_surebet_patch import dashboard_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""
    initialize()
    yield


app = FastAPI(
    title="Betano Live Analyzer",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(arbitrage_router)
app.include_router(bookmakers_router)
app.include_router(health_router)
app.include_router(model_router)
app.include_router(oddspapi_router)
app.include_router(provider_accounts_router)
app.include_router(telegram_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "betano-live-analyzer"}


@app.get("/", include_in_schema=False)
def dashboard():
    return dashboard_response(date.today())


@app.get("/panel", include_in_schema=False)
def control_panel():
    return control_panel_page()


@app.get("/bookmakers", include_in_schema=False)
def bookmakers_panel():
    return bookmakers_panel_page()


@app.get("/provider-accounts", include_in_schema=False)
def provider_accounts():
    return provider_accounts_page()


@app.get("/telegram-test", include_in_schema=False)
def telegram_test():
    return telegram_test_page()
