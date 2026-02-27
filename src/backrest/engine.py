# src/backtest/engine.py

from decimal import Decimal
from datetime import datetime
from typing import Dict, Any

from src.polymarket.client import PolymarketSimulatorClient, Order
from src.risk.manager import RiskManager


class BacktestEngine:

    def __init__(self, simulator, use_risk: bool = True):
        self.simulator = simulator
        self.risk_manager = RiskManager() if use_risk else None
        self.client = PolymarketSimulatorClient(
            simulator,
            risk_manager=self.risk_manager
        )

        self.trades_attempted = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        self.kill_switch_triggered = False
        self.equity_curve = []
        self.max_drawdown = Decimal("0.0")

    async def run(self, steps: int = 10) -> Dict[str, Any]:

        equity = Decimal("0.0")
        peak = Decimal("0.0")

        for _ in range(steps):

            self.trades_attempted += 1

            order = Order(
                market_id="sim-1",
                side="YES",
                size=Decimal("1.0"),
                price=Decimal("0.55"),
            )

            result = await self.client.place_order(order)

            if result["status"] == "rejected":
                self.trades_rejected += 1
                continue

            self.trades_executed += 1

            # Equity negativa simplificada (coste compra)
            executed_size = Decimal(str(result["filled_size"]))
            executed_price = Decimal(str(result["executed_price"]))

            pnl = -(executed_size * executed_price)
            equity += pnl

            # Drawdown
            if equity > peak:
                peak = equity

            drawdown = peak - equity
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

            self.equity_curve.append(equity)

            if self.risk_manager and self.risk_manager.kill_switch:
                self.kill_switch_triggered = True
                break

        return self._results()

    def _results(self) -> Dict[str, Any]:
        return {
            "performance": {
                "trades_attempted": self.trades_attempted,
                "trades_executed": self.trades_executed,
                "trades_rejected": self.trades_rejected,
                "max_drawdown": str(self.max_drawdown),
                "kill_switch_triggered": self.kill_switch_triggered,
            },
            "results": {
                "equity_curve": [str(e) for e in self.equity_curve],
            },
        }
