# tests/test_client_risk_integration.py

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from market_simulator import MarketSimulator
from src.polymarket.client import PolymarketSimulatorClient, Order
from src.risk.manager import RiskManager


# ==============================
# FIXTURE BASE
# ==============================

@pytest.fixture
def sim():
    return MarketSimulator(real_time_sleep=False)


@pytest.fixture
def risk():
    return RiskManager()


@pytest.fixture
def client(sim, risk):
    return PolymarketSimulatorClient(sim, risk_manager=risk)


# ==============================
# 1️⃣ Rechazo por Kill Switch
# ==============================

@pytest.mark.asyncio
async def test_rejected_due_to_kill_switch(client, risk):

    risk.force_kill_switch()

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.50"),
    )

    result = await client.place_order(order)

    assert result["status"] == "rejected"
    assert "Kill switch" in result["reason"]


# ==============================
# 2️⃣ Rechazo por Cooldown
# ==============================

@pytest.mark.asyncio
async def test_rejected_due_to_cooldown(client, risk):

    # Provocar pérdida
    risk.record_result(Decimal("-1.0"))

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.50"),
    )

    result = await client.place_order(order)

    assert result["status"] == "rejected"
    assert "Cooldown" in result["reason"]


# ==============================
# 3️⃣ PnL registrado tras fill
# ==============================

@pytest.mark.asyncio
async def test_pnl_recorded_after_fill(client, risk):

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.50"),
    )

    initial_pnl = risk.daily_pnl

    result = await client.place_order(order)

    assert result["status"] in ["filled", "partial"]
    assert risk.daily_pnl < initial_pnl  # Compra genera PnL negativo


# ==============================
# 4️⃣ Límite diario de trades
# ==============================

@pytest.mark.asyncio
async def test_daily_limit_blocks_trades(client, risk):

    # Simular 4 operaciones
    for _ in range(risk.MAX_TRADES_PER_DAY):
        risk.record_result(Decimal("-0.1"))
        risk.cooldown_until = datetime.utcnow()

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.50"),
    )

    result = await client.place_order(order)

    assert result["status"] == "rejected"
    assert "Límite diario" in result["reason"]


# ==============================
# 5️⃣ Kill Switch por pérdida acumulada
# ==============================

@pytest.mark.asyncio
async def test_kill_switch_triggered_by_client_flow(client, risk):

    # Forzar estado cercano al límite
    risk.daily_pnl = Decimal("-5.50")

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.60"),
    )

    await client.place_order(order)

    assert risk.kill_switch is True


# ==============================
# 6️⃣ Reset automático por cambio UTC
# ==============================

@pytest.mark.asyncio
async def test_auto_reset_on_new_day(client, risk):

    risk.record_result(Decimal("-2.00"))

    # Simular cambio de día
    risk.current_day = risk.current_day - timedelta(days=1)

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("0.5"),
        price=Decimal("0.50"),
    )

    await client.place_order(order)

    # Debe haberse reseteado automáticamente
    assert risk.trade_count == 1
    assert risk.daily_pnl < Decimal("0")
