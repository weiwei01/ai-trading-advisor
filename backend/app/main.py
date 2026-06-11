"""FastAPI 進入點。

重要定位：本系統為「AI 決策輔助」，非自動化交易。
任何 API 都不會送出委託單；最終是否送單由人類於券商端自行執行。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import get_connection, init_db
from app.routers import backtest, portfolio, proposals


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables and metadata seed
    conn = get_connection()
    init_db(conn)
    conn.close()
    yield
    # Shutdown: clean up if needed


app = FastAPI(
    title="AI Trading Advisor",
    description="台股 AI 決策輔助系統（非自動化交易，下單由人類負責）",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proposals.router)
app.include_router(portfolio.router)
app.include_router(backtest.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "advisory-only"}
