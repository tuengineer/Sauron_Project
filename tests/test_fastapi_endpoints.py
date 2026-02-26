# tests/test_fastapi_endpoints.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from decimal import Decimal
from src.main import app
from polymarket import Order

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "simulation_running" in data

@pytest.mark.asyncio
async def test_kill_switch_toggle():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Activar
        r_on = await ac.post("/kill-switch", params={"active": True})
        assert r_on.status_code == 200
        assert r_on.json()["kill_switch"] is True
        # Desactivar
        r_off = await ac.post("/kill-switch", params={"active": False})
        assert r_off.status_code == 200
        assert r_off.json()["kill_switch"] is False

@pytest.mark.asyncio
async def test_status_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert "kill_switch" in data
        assert "used_today" in data

@pytest.mark.asyncio
async def test_simulation_start_stop():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r_start = await ac.post("/simulate/start")
        assert r_start.status_code == 200
        assert r_start.json()["status"] in ["started", "already_running"]

        r_stop = await ac.post("/simulate/stop")
        assert r_stop.status_code == 200
        assert r_stop.json()["status"] == "stopped"

@pytest.mark.asyncio
async def test_simulation_regime_and_quote():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r_regime = await ac.post("/simulate/regime/sim-1", params={"regime": "HIGH"})
        assert r_regime.status_code == 200
        assert r_regime.json()["regime"] == "HIGH"

        r_quote = await ac.get("/simulate/quote/sim-1")
        assert r_quote.status_code == 200
        q = r_quote.json()
        assert "bid" in q and "ask" in q

@pytest.mark.asyncio
async def test_simulation_stats():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/simulate/stats/sim-1")
        assert r.status_code == 200
        stats = r.json()
        assert "market_id" in stats
        assert "stats" in stats

@pytest.mark.asyncio
async def test_simulate_trade_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/simulate/trade", params={
            "market_id": "sim-1",
            "side": "YES",
            "size": 1.0,
            "price": 0.55
        })
        assert r.status_code == 200
        order = r.json()["order"]
        assert order["status"] in ["filled", "partial"]
        assert order["size_filled"] > 0
        assert order["price_executed"] is not None

@pytest.mark.asyncio
async def test_backtest_run():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/backtest/run", params={"duration_minutes": 1, "regime": "NORMAL"})
        assert r.status_code == 200
        data = r.json()
        assert "performance" in data
        assert "results" in data
        assert data["backtest_config"]["steps_executed"] == 1
