# F:\Sauron_Project\src\backtest\engine.py

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.market_simulator.core import MarketSimulator
from src.risk.manager import RiskManager, RiskException


logger = logging.getLogger("BACKTEST_ENGINE")


# ==========================================
# DATA STRUCTURES
# ==========================================

@dataclass
class BacktestTrade:
    timestamp: datetime
    side: str
    price: float
    size: float
    pnl: float
    balance_after: float


@dataclass
class BacktestResult:
    initial_balance: float
    final_balance: float
    total_return_pct: float
    total_trades: int
    win_rate: float
    max_drawdown_pct: float
    trades: List[BacktestTrade]


# ==========================================
# BACKTEST ENGINE
# ==========================================

class BacktestEngine:

    def __init__(
        self,
        historical_data: List[Dict[str, Any]],
        initial_balance: float = 1000.0,
        position_size: float = 10.0,
    ):
        """
        :param historical_data: Lista de snapshots de mercado ordenados por tiempo.
        :param initial_balance: Balance inicial para el backtest.
        :param position_size: Tamaño fijo por operación.
        """
        self.historical_data = historical_data
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position_size = position_size

        self.simulator = MarketSimulator()
        self.risk_manager = RiskManager()

        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = []

        self.current_position: Optional[Dict[str, Any]] = None

    # ==========================================
    # CORE EXECUTION
    # ==========================================

    def run(self) -> BacktestResult:
        logger.info("Starting backtest")

        for snapshot in self.historical_data:
            self._process_snapshot(snapshot)

        final_balance = self.balance
        total_return_pct = (
            (final_balance - self.initial_balance) / self.initial_balance
        ) * 100.0

        win_trades = [t for t in self.trades if t.pnl > 0]
        win_rate = (
            len(win_trades) / len(self.trades) * 100.0
            if self.trades
            else 0.0
        )

        max_drawdown_pct = self._calculate_max_drawdown()

        logger.info("Backtest completed")

        return BacktestResult(
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_return_pct=round(total_return_pct, 2),
            total_trades=len(self.trades),
            win_rate=round(win_rate, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            trades=self.trades,
        )

    # ==========================================
    # SNAPSHOT PROCESSING
    # ==========================================

    def _process_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Ejecuta lógica sobre cada snapshot histórico.
        """
        decision = self.simulator.evaluate_market(snapshot)

        if decision:
            try:
                self.risk_manager.validate(decision)
                self._execute_trade(decision, snapshot)
            except RiskException:
                logger.debug("Trade blocked by risk manager during backtest")

        self.equity_curve.append(self.balance)

    # ==========================================
    # TRADE EXECUTION
    # ==========================================

    def _execute_trade(self, decision: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
        """
        Simula ejecución inmediata al precio del snapshot.
        Se asume snapshot["price"] disponible.
        """

        price = float(snapshot.get("price", 0))
        side = decision.get("side", "BUY")
        timestamp = snapshot.get("timestamp", datetime.utcnow())

        if price <= 0:
            return

        size = self.position_size

        # Si no hay posición abierta → abrir
        if self.current_position is None:
            self.current_position = {
                "side": side,
                "entry_price": price,
                "size": size,
                "timestamp": timestamp,
            }
            return

        # Si hay posición → cerrar
        entry_price = self.current_position["entry_price"]
        entry_side = self.current_position["side"]

        pnl = self._calculate_pnl(
            entry_side=entry_side,
            entry_price=entry_price,
            exit_price=price,
            size=size,
        )

        self.balance += pnl

        trade = BacktestTrade(
            timestamp=timestamp,
            side=entry_side,
            price=price,
            size=size,
            pnl=round(pnl, 4),
            balance_after=round(self.balance, 4),
        )

        self.trades.append(trade)
        self.current_position = None

    # ==========================================
    # PNL CALCULATION
    # ==========================================

    @staticmethod
    def _calculate_pnl(
        entry_side: str,
        entry_price: float,
        exit_price: float,
        size: float,
    ) -> float:
        if entry_side.upper() == "BUY":
            return (exit_price - entry_price) * size
        else:
            return (entry_price - exit_price) * size

    # ==========================================
    # MAX DRAWDOWN
    # ==========================================

    def _calculate_max_drawdown(self) -> float:
        peak = self.initial_balance
        max_dd = 0.0

        for equity in self.equity_curve:
            if equity > peak:
                peak = equity

            drawdown = (peak - equity) / peak * 100.0
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd
