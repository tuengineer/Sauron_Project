# src/market_simulator/core.py

import asyncio
import time
from decimal import Decimal
from typing import Callable, List, Dict, Any, Optional

from .orderbook import OrderBookL2
from .latency_model import LatencyModel
from .flow_generator import FlowGenerator, VolatilityRegime
from .events import EventEngine


class MarketSimulator:
    """
    Motor institucional L2.
    """

    def __init__(self, real_time_sleep: bool = False):
        self.real_time_sleep = real_time_sleep

        self.book = OrderBookL2()
        self.latency = LatencyModel()
        self.flow = FlowGenerator()
        self.events = EventEngine()

        self.trade_history: List[Dict[str, Any]] = []
        self.current_time_ms: int = 0

        self.on_trade: Optional[Callable] = None
        self.on_book_update: Optional[Callable] = None

    # =====================================================
    # Régimen dinámico
    # =====================================================

    def set_volatility_regime(self, regime: str):
        self.flow.set_regime(regime)

    # =====================================================
    # Core execution
    # =====================================================

    async def run_step(self, duration_ms: int):
        """
        Ejecuta un bloque de simulación de duration_ms.
        """

        orders = self.flow.generate_orders_for_step(duration_ms)

        for order in orders:
            self.current_time_ms += order["offset_ms"]

            self.events.maybe_inject_event(self.current_time_ms)

            self.book.consume_market_order(
                order["side"],
                order["size"]
            )

            trade = {
                "timestamp_ms": self.current_time_ms,
                "side": order["side"],
                "size": order["size"],
                "price": (
                    self.book.best_ask().price
                    if order["side"] == "buy"
                    else self.book.best_bid().price
                ),
                "informed": order["informed"]
            }

            self.trade_history.append(trade)

            if self.on_trade:
                self.on_trade(trade)

            if self.on_book_update:
                self.on_book_update(self.book.get_depth())

        self.current_time_ms += duration_ms

        latency_ms = self.latency.sample()

        if self.real_time_sleep:
            await asyncio.sleep(latency_ms / 1000.0)

    # =====================================================
    # Estadísticas DeepSeek
    # =====================================================

    def get_simulation_stats(self) -> Dict[str, Any]:
        total_trades = len(self.trade_history)

        if total_trades == 0:
            return {
                "total_trades": 0,
                "volume": 0,
                "avg_trade_size": 0,
                "buy_ratio": 0
            }

        volume = sum(t["size"] for t in self.trade_history)
        avg_size = volume / Decimal(total_trades)
        buy_count = sum(1 for t in self.trade_history if t["side"] == "buy")

        return {
            "total_trades": total_trades,
            "volume": float(volume),
            "avg_trade_size": float(avg_size),
            "buy_ratio": buy_count / total_trades
        }
