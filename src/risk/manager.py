# risk/manager.py
from typing import Dict, Any

class RiskManager:
    # ==============================
    # CONSTANTES FASE 1
    # ==============================
    MAX_COST_PER_TRADE = 2.50
    DAILY_LOSS_LIMIT = -50.0
    DAILY_LOSS_KILL_SWITCH = -100.0
    COOLDOWN_DURATION = 3600  # segundos

    # ==============================
    # INIT
    # ==============================
    def __init__(self, phase: int = 1):
        self.phase = phase
        self.daily_pnl = 0.0
        self.cooldown_until = 0
        self.kill_switch = False

    # ==============================
    # MÉTODOS PRINCIPALES
    # ==============================
    def validate_trade(self, size: float, price: float, icm: float) -> Dict[str, Any]:
        """
        Validación completa de una orden.
        Devuelve dict con keys: approved (bool), reason (str)
        """
        if self.kill_switch or self._in_cooldown():
            return {"approved": False, "reason": "Kill switch o cooldown activo"}
        cost = size * price
        if cost > self.MAX_COST_PER_TRADE:
            return {"approved": False, "reason": "Costo por trade excede límite"}
        if self.daily_pnl + cost < self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
            return {"approved": False, "reason": "Límite diario de pérdida excedido, kill switch activado"}
        return {"approved": True, "reason": "Trade aprobado"}

    def record_result(self, pnl: float) -> None:
        """
        Registrar PnL de orden ejecutada.
        Actualiza daily_pnl, activa cooldown si es necesario.
        """
        self.daily_pnl += pnl
        if self.daily_pnl < self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
            print(f"[KILL_SWITCH] Activado automáticamente, daily_pnl={self.daily_pnl}")
        else:
            self.cooldown_until = 0  # reset cooldown si PnL positivo

    def can_trade(self) -> bool:
        """
        Check rápido si se puede operar.
        """
        return not self.kill_switch and not self._in_cooldown()

    def get_status(self) -> Dict[str, Any]:
        """
        Estado completo del RiskManager.
        """
        return {
            "daily_pnl": self.daily_pnl,
            "kill_switch": self.kill_switch,
            "cooldown_until": self.cooldown_until,
            "can_trade": self.can_trade()
        }

    def reset_daily(self) -> None:
        """
        Reset diario de contadores y kill switch.
        """
        self.daily_pnl = 0.0
        self.kill_switch = False
        self.cooldown_until = 0
        print("[RESET_DAILY] Estado diario reseteado")

    # ==============================
    # API PÚBLICA AUXILIAR
    # ==============================
    def force_kill_switch(self) -> None:
        """
        Fuerza la activación manual del kill switch vía API.
        Útil para parada de emergencia operada por humano.
        """
        self.daily_pnl = self.DAILY_LOSS_KILL_SWITCH
        self.kill_switch = True
        print(f"[KILL_SWITCH_FORCED] daily_pnl set to {self.daily_pnl}")

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
        import time
        return time.time() < self.cooldown_until

    def _reject(self, reason: str) -> Dict[str, Any]:
        return {"approved": False, "reason": reason}
