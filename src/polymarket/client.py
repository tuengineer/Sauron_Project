# src/polymarket/client.py
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
from .models import Market, OrderBook, OrderBookLevel, Order
from ..market_simulator.core import MarketSimulator

class PolymarketClientError(Exception):
    """Error específico de operaciones Polymarket"""
    pass

class PolymarketSimulatorClient:
    def __init__(self, simulator: MarketSimulator):
        self.sim = simulator

    # =====================================================
    # Métodos públicos
    # =====================================================
    async def list_markets(self, tags: Optional[List[str]] = None) -> List[Market]:
        quote = self.sim.book.get_depth(levels=1)
        mid = (quote["bids"][0].price + quote["asks"][0].price) / 2 if quote["bids"] else Decimal("0.5")

        market = Market(
            id=getattr(self.sim.book, "market_id", "sim-1"),
            title=f"Simulated Market {id(self.sim)}",
            tags=["crypto", "simulated"],
            yes_price=mid,
            no_price=Decimal("1") - mid,
            volume=sum(t["size"] for t in self.sim.trade_history),
            liquidity=sum(l[1] for l in self.sim.book.asks) + sum(l[1] for l in self.sim.book.bids),
            resolution_date=datetime.utcnow() + timedelta(days=30),
            status="active"
        )

        if tags and not any(t in market.tags for t in tags):
            return []
        return [market]

    async def get_orderbook(self, market_id: str) -> OrderBook:
        if market_id != getattr(self.sim.book, "market_id", "sim-1"):
            raise PolymarketClientError(f"Market {market_id} not found")

        depth = self.sim.book.get_depth(levels=5)

        return OrderBook(
            market_id=market_id,
            bids=[OrderBookLevel(price=b.price, size=b.size) for b in depth["bids"]],
            asks=[OrderBookLevel(price=a.price, size=a.size) for a in depth["asks"]],
            timestamp_ms=self.sim.current_time_ms
        )

    async def place_order(self, order: Order) -> Order:
        """
        Ejecuta orden contra el libro del simulador.
        
        NOTA: Validación de riesgo ahora ocurre en main.py antes de llamar este método.
        Este cliente es "tonto" — solo ejecuta, no valida.
        """

        side_map = {"YES": "buy", "NO": "sell"}
        sim_side = side_map.get(order.side, order.side.lower())

        execution = self.sim.book.consume_market_order(sim_side, order.size)

        # Actualizar order
        order.filled_size = execution["executed_size"]
        order.remaining_size = execution["remaining"]
        order.executed_price = execution["avg_price"]
        order.slippage = execution["slippage_bps"] / Decimal("10000")
        order.status = "filled" if execution["remaining"] == 0 else "partial"
        order.latency_ms = self.sim.latency.sample()

        # ==============================
        # CÁLCULO SIMPLE DE PnL
        # ==============================
        realized_pnl = Decimal("0")
        if order.executed_price and order.filled_size > 0:
            depth = self.sim.book.get_depth(levels=1)
            if depth["bids"] and depth["asks"]:
                mid = (depth["bids"][0].price + depth["asks"][0].price) / Decimal("2")
                if order.side == "YES":
                    realized_pnl = (mid - order.executed_price) * order.filled_size
                else:  # NO
                    realized_pnl = (order.executed_price - mid) * order.filled_size

        order.realized_pnl = realized_pnl.quantize(Decimal("0.0001"))

        # Registrar trade
        self.sim.trade_history.append({
            "timestamp_ms": self.sim.current_time_ms,
            "order_side": order.side,
            "size": order.filled_size,
            "price": order.executed_price,
            "slippage_bps": execution["slippage_bps"],
            "agent_order": True,
            "realized_pnl": order.realized_pnl
        })

        return order

    async def get_portfolio(self, wallet_address: str) -> List[Order]:
        return []

    def get_simulator_stats(self, market_id: Optional[str] = None) -> Dict[str, Any]:
        return self.sim.get_simulation_stats()
