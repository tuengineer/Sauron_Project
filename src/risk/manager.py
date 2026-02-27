# src/risk/manager.py

from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, date
from typing import Dict, Any


class RiskManager:
    # ==============================
    # CONSTANTES FASE 1
    # ==============================
    MAX_COST_PER_TRADE = Decimal("2.50")
    ICM_MIN = Decimal("0.70")
    DAILY_LOSS_LIMIT = Decimal("-6.00")
    COOLDOWN_DURATION = 4 * 3600  # 4 horas
    ANTI_FOMO_MINUTES = 30
    MAX_TRADES_PER_DAY = 4

    # ==============================
    # INIT
    # ==============================
    def __init__(self, phase: int = 1):
        self.phase = phase
        self.daily_pnl = Decimal("0.00")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None
        self.current_day = datetime.utcnow().date()

    # ==============================
    # MÉTODOS PRINCIPALES
    # ==============================

    def validate_trade(self, size: float, price: float, icm: Decimal) -> Dict[str, Any]:
        """
        Validación completa de una orden.
        Devuelve dict con keys: approved (bool), reason (str)
        """

        self._auto_reset_if_new_day()
        now = datetime.utcnow()

        # Kill switch
        if self.kill_switch:
            return self._reject("Kill switch activo")

        # Cooldown
        if self._in_cooldown():
            return self._reject("Cooldown activo")

        # Validación datos corruptos
        if not self._valid_market_inputs(size, price, icm):
            return self._reject("Datos de mercado inválidos")

        size_dec = Decimal(str(size))
        price_dec = Decimal(str(price))

        # Límite trades diarios
        if self.trade_count >= self.MAX_TRADES_PER_DAY:
            return self._reject("Límite diario de trades alcanzado")

        # ICM mínimo
        if icm < self.ICM_MIN:
            return self._reject(f"ICM {icm} menor que mínimo {self.ICM_MIN}")

        # Anti-FOMO
        if (
            self.last_trade_time
            and (now - self.last_trade_time).total_seconds()
            < self.ANTI_FOMO_MINUTES * 60
        ):
            return self._reject("Anti-FOMO: esperar 30 min entre trades")

        # Coste máximo por trade
        cost = (size_dec * price_dec).quantize(Decimal("0.0001"))
        if cost > self.MAX_COST_PER_TRADE:
            return self._reject("Costo por trade excede límite")

        return {"approved": True, "reason": "Trade aprobado"}

    def record_result(self, pnl: Decimal) -> None:
        """
        Registrar PnL de orden ejecutada.
        """

        self._auto_reset_if_new_day()

        pnl = Decimal(str(pnl)).quantize(Decimal("0.0001"))

        self.daily_pnl = (self.daily_pnl + pnl).quantize(Decimal("0.0001"))
        self.trade_count += 1
        self.last_trade_time = datetime.utcnow()

        # Kill switch automático
        if self.daily_pnl <= self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
            return

        # Cooldown tras pérdida
        if pnl < 0:
            self.cooldown_until = datetime.utcnow() + timedelta(
                seconds=self.COOLDOWN_DURATION
            )

    def can_trade(self) -> bool:
        self._auto_reset_if_new_day()
        now = datetime.utcnow()
        return (
            not self.kill_switch
            and now >= self.cooldown_until
            and self.trade_count < self.MAX_TRADES_PER_DAY
        )

    def get_status(self) -> Dict[str, Any]:
        self._auto_reset_if_new_day()
        return {
            "daily_pnl": self.daily_pnl,
            "trade_count": self.trade_count,
            "kill_switch": self.kill_switch,
            "cooldown_until": self.cooldown_until,
            "can_trade": self.can_trade(),
        }

    def reset_daily(self) -> None:
        self.daily_pnl = Decimal("0.00")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None
        self.current_day = datetime.utcnow().date()

    # ==============================
    # PERSISTENCIA (AUDITOR READY)
    # ==============================

    def export_state(self) -> Dict[str, Any]:
        return {
            "daily_pnl": str(self.daily_pnl),
            "trade_count": self.trade_count,
            "kill_switch": self.kill_switch,
            "cooldown_until": self.cooldown_until.isoformat(),
            "last_trade_time": self.last_trade_time.isoformat()
            if self.last_trade_time
            else None,
            "current_day": self.current_day.isoformat(),
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        self.daily_pnl = Decimal(state["daily_pnl"])
        self.trade_count = state["trade_count"]
        self.kill_switch = state["kill_switch"]
        self.cooldown_until = datetime.fromisoformat(state["cooldown_until"])
        self.last_trade_time = (
            datetime.fromisoformat(state["last_trade_time"])
            if state["last_trade_time"]
            else None
        )
        self.current_day = date.fromisoformat(state["current_day"])

    # ==============================
    # API PÚBLICA AUXILIAR
    # ==============================

    def force_kill_switch(self) -> None:
        self.daily_pnl = self.DAILY_LOSS_LIMIT
        self.kill_switch = True

    def manual_reset(self) -> None:
        self.reset_daily()

    # ==============================
    # MÉTODOS PRIVADOS
    # ==============================

    def _auto_reset_if_new_day(self):
        today = datetime.utcnow().date()
        if today != self.current_day:
            self.reset_daily()

    def _valid_market_inputs(self, size, price, icm) -> bool:
        try:
            size_dec = Decimal(str(size))
            price_dec = Decimal(str(price))
            icm_dec = Decimal(str(icm))

            if size_dec <= 0 or price_dec <= 0:
                return False
            if icm_dec < 0 or icm_dec > 1:
                return False

            return True
        except (InvalidOperation, TypeError):
            return False

    def _in_cooldown(self) -> bool:
        return datetime.utcnow() < self.cooldown_until

    def _reject(self, reason: str) -> Dict[str, Any]:
        return {"approved": False, "reason": reason}
