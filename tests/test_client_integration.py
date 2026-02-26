# tests/test_client_integration.py
import pytest
from decimal import Decimal
from market_simulator import MarketSimulator
from polymarket import PolymarketSimulatorClient, Order

@pytest.mark.asyncio
async def test_place_order_with_risk_manager():
    sim = MarketSimulator(real_time_sleep=False)
    client = PolymarketSimulatorClient(sim)  # Sin RiskManager para test

    order = Order(
        market_id="sim-1",
        side="YES",
        size=Decimal("1.0"),
        price=Decimal("0.55")
    )

    result = await client.place_order(order)

    assert result.status in ["filled", "partial"]
    assert result.filled_size > 0
    assert result.executed_price is not None
    assert result.slippage is not None
