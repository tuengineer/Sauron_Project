# risk/manager.py
from decimal import Decimal
from datetime import datetime, timedelta
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
        self.daily_pnl = Decimal("0.0")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None

    # ==============================
    # MÉTODOS PRINCIPALES
    # ==============================
    def validate_trade(self, size: float, price: float, icm: Decimal) -> Dict[str, Any]:
        """
        Validación completa de una orden.
        Devuelve dict con keys: approved (bool), reason (str)
        """
        now = datetime.utcnow()
        if self.kill_switch:
            return {"approved": False, "reason": "Kill switch activo"}
        if self.trade_count >= self.MAX_TRADES_PER_DAY:
            return {"approved": False, "reason": "Límite diario de trades alcanzado"}
        if icm < self.ICM_MIN:
            return {"approved": False, "reason": f"ICM {icm} menor que mínimo {self.ICM_MIN}"}
        if self.last_trade_time and (now - self.last_trade_time).total_seconds() < self.ANTI_FOMO_MINUTES * 60:
            return {"approved": False, "reason": "Anti-FOMO: esperar 30 min entre trades"}
        if size * price > self.MAX_COST_PER_TRADE:
            return {"approved": False, "reason": "Costo por trade excede límite"}
        if self.daily_pnl + (size * price) < self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
            return {"approved": False, "reason": "Límite diario de pérdida excedido, kill switch activado"}

        return {"approved": True, "reason": "Trade aprobado"}

    def record_result(self, pnl: Decimal) -> None:
        """
        Registrar PnL de orden ejecutada.
        Actualiza daily_pnl, cooldown, kill switch si es necesario
        """
        self.daily_pnl += pnl
        self.trade_count += 1
        self.last_trade_time = datetime.utcnow()
        if self.daily_pnl < self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
        else:
            self.cooldown_until = datetime.utcnow() + timedelta(seconds=0)

    def can_trade(self) -> bool:
        """
        Check rápido si se puede operar.
        """
        now = datetime.utcnow()
        return not self.kill_switch and now >= self.cooldown_until and self.trade_count < self.MAX_TRADES_PER_DAY

    def get_status(self) -> Dict[str, Any]:
        """
        Estado completo del RiskManager.
        """
        return {
            "daily_pnl": self.daily_pnl,
            "trade_count": self.trade_count,
            "kill_switch": self.kill_switch,
            "cooldown_until": self.cooldown_until,
            "can_trade": self.can_trade()
        }

    def reset_daily(self) -> None:
        """
        Reset diario de contadores y kill switch.
        """
        self.daily_pnl = Decimal("0.0")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None
        print("[RESET_DAILY] Estado diario reseteado")

    # ==============================
    # API PÚBLICA AUXILIAR
    # ==============================
    def force_kill_switch(self) -> None:
        """
        Fuerza la activación manual del kill switch vía API.
        Útil para parada de emergencia operada por humano.
        """
        self.daily_pnl = self.DAILY_LOSS_LIMIT
        self.kill_switch = True
        print(f"[KILL_SWITCH_FORCED] daily_pnl={self.daily_pnl}")

    def manual_reset(self) -> None:
        """
        Reset manual completo del estado de riesgo.
        Desactiva kill switch, cooldown, y limpia contadores.
        """
        self.reset_daily()
        print("[MANUAL_RESET] RiskManager reseteado por operador")

    # ==============================
    # MÉTODOS PRIVADOS
    # ==============================
    def _in_cooldown(self) -> bool:
        return datetime.utcnow() < self.cooldown_until

    def _reject(self, reason: str) -> Dict[str, Any]:
        return {"approved": False, "reason": reason}
