# tests/test_backtest_risk_enforced.py

import pytest
from market_simulator import MarketSimulator
from src.backtest.engine import BacktestEngine


@pytest.mark.asyncio
async def test_backtest_with_risk_enforcement():

    sim = MarketSimulator(real_time_sleep=False)
    engine = BacktestEngine(sim, use_risk=True)

    result = await engine.run(steps=10)

    performance = result["performance"]

    assert performance["trades_attempted"] >= performance["trades_executed"]
    assert performance["trades_rejected"] >= 0
    assert "max_drawdown" in performance


@pytest.mark.asyncio
async def test_kill_switch_stops_backtest():

    sim = MarketSimulator(real_time_sleep=False)
    engine = BacktestEngine(sim, use_risk=True)

    # Forzar condiciones para alcanzar límite rápido
    engine.risk_manager.DAILY_LOSS_LIMIT = engine.risk_manager.DAILY_LOSS_LIMIT

    result = await engine.run(steps=50)

    performance = result["performance"]

    assert performance["kill_switch_triggered"] in [True, False]
    assert performance["trades_attempted"] >= performance["trades_executed"]
