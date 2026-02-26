# tests/test_execution_price.py

from decimal import Decimal
from market_simulator.orderbook import OrderBookL2


def test_execution_price_is_weighted_average():
    book = OrderBookL2(mid_price=Decimal("0.50"))

    # Forzar estructura conocida
    # Asks: 0.51 (100), 0.52 (100)
    book.asks = [
        (Decimal("0.51"), Decimal("100")),
        (Decimal("0.52"), Decimal("100")),
    ]

    result = book.consume_market_order("buy", Decimal("150"))

    # VWAP esperado:
    # (100 * 0.51 + 50 * 0.52) / 150
    expected_vwap = (
        (Decimal("100") * Decimal("0.51") +
         Decimal("50") * Decimal("0.52"))
        / Decimal("150")
    ).quantize(Decimal("0.0001"))

    assert result["executed_size"] == Decimal("150")
    assert result["avg_price"] == expected_vwap
    assert result["slippage_bps"] > 0
    assert result["remaining"] == Decimal("0")
