from decimal import Decimal, getcontext
from datetime import datetime, timedelta
from typing import Dict, Optional

# Alta precisión decimal
getcontext().prec = 28


class RiskManager:
    """
    RiskManager v2.0 - Fase 1 Conservadora

    Sistema de control de riesgo basado en:
    - Costo real por trade (size × price)
    - Límite diario de pérdidas
    - Cooldown tras pérdida
    - Anti-FOMO timing
    - Límite máximo de trades diarios
    - Filtro de calidad ICM

    Todas las operaciones monetarias usan Decimal.
    """

    # ==============================
    # FASE 1 CONFIGURACIÓN
    # ==============================

    MAX_COST_PER_TRADE = Decimal("2.50")
    DAILY_BUDGET = Decimal("10.00")
    MAX_TRADES_PER_DAY = 4

    ICM_MIN = Decimal("0.70")

    DAILY_LOSS_KILL_SWITCH = Decimal("-6.00")
    CONSECUTIVE_LOSSES_MAX = 1
    COOLDOWN_DURATION_HOURS = 4
    MIN_TIME_BETWEEN_TRADES_MIN = 30

    def __init__(self, phase: int = 1):
        """
        :param phase: Preparado para futuras fases (actualmente solo Fase 1)
        """
        self.phase = phase

        # Estado diario
        self.daily_pnl: Decimal = Decimal("0.00")
        self.daily_trades: int = 0
        self.consecutive_losses: int = 0

        self.cooldown_until: Optional[datetime] = None
        self.last_trade_time: Optional[datetime] = None

    # ==========================================================
    # MÉTODO PRINCIPAL DE VALIDACIÓN
    # ==========================================================

    def validate_trade(
        self,
        size: Decimal,
        price: Decimal,
        icm: Decimal
    ) -> Dict:
        """
        Valida si un trade puede ejecutarse bajo reglas de riesgo Fase 1.

        :param size: Exposición nominal
        :param price: Precio del mercado
        :param icm: Índice de Credibilidad de Mercado
        :return: dict {"approved": bool, "reason": str, "cost": Decimal}
        """

        now = datetime.utcnow()
        cost = (size * price).quantize(Decimal("0.0001"))

        # 1️⃣ ICM
        if icm < self.ICM_MIN:
            return self._reject(
                reason=f"ICM_TOO_LOW",
                extra=f"icm={icm} threshold={self.ICM_MIN}",
                cost=cost
            )

        # 2️⃣ Cooldown
        if self._in_cooldown(now):
            remaining = int((self.cooldown_until - now).total_seconds() // 60)
            return self._reject(
                reason="COOLDOWN_ACTIVE",
                extra=f"remaining={remaining}m",
                cost=cost
            )

        # 3️⃣ Kill Switch Diario
        if self.daily_pnl <= self.DAILY_LOSS_KILL_SWITCH:
            return self._reject(
                reason="KILL_SWITCH_ACTIVE",
                extra=f"daily_pnl={self.daily_pnl} limit={self.DAILY_LOSS_KILL_SWITCH}",
                cost=cost
            )

        # 4️⃣ Anti-FOMO
        if self.last_trade_time:
            delta = now - self.last_trade_time
            if delta < timedelta(minutes=self.MIN_TIME_BETWEEN_TRADES_MIN):
                return self._reject(
                    reason="ANTI_FOMO_BLOCK",
                    extra=f"wait_more={(self.MIN_TIME_BETWEEN_TRADES_MIN - int(delta.total_seconds() // 60))}m",
                    cost=cost
                )

        # 5️⃣ Límite trades diarios
        if self.daily_trades >= self.MAX_TRADES_PER_DAY:
            return self._reject(
                reason="MAX_TRADES_REACHED",
                extra=f"trades_today={self.daily_trades}",
                cost=cost
            )

        # 6️⃣ Validación económica final (costo real)
        if cost > self.MAX_COST_PER_TRADE:
            return self._reject(
                reason="COST_EXCEEDED",
                extra=f"cost={cost} max={self.MAX_COST_PER_TRADE}",
                cost=cost
            )

        # ✅ Aprobado
        self.daily_trades += 1
        self.last_trade_time = now

        print(
            f"[APPROVED] size={size} price={price} cost={cost} "
            f"icm={icm} daily_pnl={self.daily_pnl} trades_today={self.daily_trades}"
        )

        return {
            "approved": True,
            "reason": "APPROVED",
            "cost": cost
        }

    # ==========================================================
    # REGISTRO DE RESULTADOS
    # ==========================================================

    def record_result(self, pnl: Decimal) -> None:
        """
        Registra resultado de trade cerrado.
        Activa cooldown si hay pérdida.
        """

        self.daily_pnl += pnl

        if pnl < Decimal("0"):
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Activar cooldown tras 1 pérdida
        if self.consecutive_losses >= self.CONSECUTIVE_LOSSES_MAX:
            self.cooldown_until = datetime.utcnow() + timedelta(
                hours=self.COOLDOWN_DURATION_HOURS
            )
            print(
                f"[COOLDOWN_ACTIVATED] until={self.cooldown_until.isoformat()}"
            )

        # Kill switch activado
        if self.daily_pnl <= self.DAILY_LOSS_KILL_SWITCH:
            print(
                f"[KILL_SWITCH] daily_pnl={self.daily_pnl} "
                f"limit={self.DAILY_LOSS_KILL_SWITCH}"
            )

    # ==========================================================
    # UTILIDADES INTERNAS
    # ==========================================================

    def _in_cooldown(self, now: datetime) -> bool:
        if self.cooldown_until and now < self.cooldown_until:
            return True
        return False

    def _reject(self, reason: str, extra: str, cost: Decimal) -> Dict:
        print(f"[REJECTED] reason={reason} {extra}")
        return {
            "approved": False,
            "reason": reason,
            "cost": cost
        }

    # ==========================================================
    # API PÚBLICA AUXILIAR
    # ==========================================================

    def can_trade(self) -> bool:
        """
        Check rápido sin parámetros.
        """
        now = datetime.utcnow()

        if self.daily_pnl <= self.DAILY_LOSS_KILL_SWITCH:
            return False

        if self._in_cooldown(now):
            return False

        if self.daily_trades >= self.MAX_TRADES_PER_DAY:
            return False

        return True

    def get_status(self) -> Dict:
        """
        Devuelve estado completo del búnker.
        """
        now = datetime.utcnow()
        cooldown_remaining = None

        if self.cooldown_until and now < self.cooldown_until:
            cooldown_remaining = int(
                (self.cooldown_until - now).total_seconds() // 60
            )

        return {
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_active": cooldown_remaining is not None,
            "cooldown_remaining_min": cooldown_remaining,
            "kill_switch_active": self.daily_pnl <= self.DAILY_LOSS_KILL_SWITCH
        }

    def reset_daily(self) -> None:
        """
        Reset diario (00:00 UTC).
        """
        self.daily_pnl = Decimal("0.00")
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.cooldown_until = None
        self.last_trade_time = None

        print("[DAILY_RESET] RiskManager state cleared")
