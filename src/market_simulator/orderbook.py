# src/market_simulator/orderbook.py

from decimal import Decimal
from typing import Dict
import heapq


def consume_market_order(self, side: str, size: Decimal) -> Dict[str, Decimal]:
    """
    Ejecuta orden de mercado contra el book.

    Retorna:
    {
        "executed_size": Decimal,
        "avg_price": Decimal,
        "remaining": Decimal,
        "slippage_bps": Decimal
    }
    """
    book_side = self.asks if side == "buy" else self.bids

    remaining = size
    total_cost = Decimal("0")
    executed = Decimal("0")

    # Precio pre-trade
    pre_trade_mid = self.mid_price()

    temp_levels = []

    while remaining > 0 and book_side:
        if side == "buy":
            price, liquidity = heapq.heappop(book_side)
        else:
            neg_price, liquidity = heapq.heappop(book_side)
            price = -neg_price

        if liquidity <= 0:
            continue

        take = min(remaining, liquidity)

        total_cost += take * price
        executed += take
        remaining -= take
        liquidity -= take

        if liquidity > 0:
            temp_levels.append((price, liquidity))

    # Reinsertar niveles parcialmente consumidos
    for price, liquidity in temp_levels:
        if side == "buy":
            heapq.heappush(book_side, (price, liquidity))
        else:
            heapq.heappush(book_side, (-price, liquidity))

    avg_price = (
        (total_cost / executed)
        if executed > 0
        else Decimal("0")
    )

    slippage_bps = Decimal("0")
    if executed > 0 and pre_trade_mid > 0:
        if side == "buy":
            slippage = (avg_price - pre_trade_mid) / pre_trade_mid
        else:
            slippage = (pre_trade_mid - avg_price) / pre_trade_mid

        slippage_bps = (slippage * Decimal("10000")).quantize(
            Decimal("0.01")
        )

    self._maintain_depth()

    return {
        "executed_size": executed,
        "avg_price": avg_price.quantize(Decimal("0.0001")),
        "remaining": remaining,
        "slippage_bps": slippage_bps
    }
