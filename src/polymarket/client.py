# src/polymarket/client.py

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from src.risk.manager import RiskManager


@dataclass
class Order:
    market_id: str
    side: str  # "YES" / "NO"
    size: Decimal
    price: Decimal


class PolymarketSimulatorClient:
    def __init__(self, simulator, risk_manager: Optional[RiskManager] = None):
        self.simulator = simulator
        self.risk_manager = risk_manager

    async def place_order(self, order: Order):
        """
        Flujo completo:
        1. Validación RiskManager (si existe)
        2. Ejecución en simulador
        3. Registro PnL en RiskManager
        """

        # ==============================
        # 1️⃣ VALIDACIÓN RISK
        # ==============================
        if self.risk_manager:

            validation = self.risk_manager.validate_trade(
                size=float(order.size),
                price=float(order.price),
                icm=Decimal("1.0"),  # En simulación asumimos ICM óptimo
            )

            if not validation["approved"]:
                return self._rejected_order(validation["reason"], order)

        # ==============================
        # 2️⃣ EJECUCIÓN EN SIMULADOR
        # ==============================
        result = await self.simulator.execute_order(
            market_id=order.market_id,
            side=order.side,
            size=order.size,
            price=order.price,
        )

        # ==============================
        # 3️⃣ REGISTRO PnL
        # ==============================
        if self.risk_manager and result["status"] in ["filled", "partial"]:

            executed_size = Decimal(str(result["filled_size"]))
            executed_price = Decimal(str(result["executed_price"]))

            # PnL simplificado simulación:
            # Si compra (YES) pagamos precio → riesgo negativo
            pnl = -(executed_size * executed_price)

            self.risk_manager.record_result(pnl)

        return result

    # ==============================
    # MÉTODO AUXILIAR
    # ==============================

    def _rejected_order(self, reason: str, order: Order):
        return {
            "status": "rejected",
            "reason": reason,
            "market_id": order.market_id,
            "side": order.side,
            "filled_size": Decimal("0"),
            "executed_price": None,
            "slippage": None,
        }
