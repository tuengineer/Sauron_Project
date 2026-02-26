# src/market_simulator/core.py

execution = self.book.consume_market_order(
    order["side"],
    order["size"]
)

trade = {
    "timestamp_ms": self.current_time_ms,
    "side": order["side"],
    "size": execution["executed_size"],          # REAL
    "avg_price": execution["avg_price"],        # VWAP REAL
    "slippage_bps": execution["slippage_bps"],  # Nuevo
    "remaining": execution["remaining"],        # Parcial fill
    "informed": order["informed"]
}

self.trade_history.append(trade)
