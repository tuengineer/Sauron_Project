# src/risk/manager.py

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from datetime import datetime, timedelta, date
from typing import Dict, Any


class RiskManager:

    MAX_COST_PER_TRADE = Decimal("2.50")
    ICM_MIN = Decimal("0.70")
    DAILY_LOSS_LIMIT = Decimal("-6.00")
    COOLDOWN_DURATION = 4 * 3600
    ANTI_FOMO_MINUTES = 30
    MAX_TRADES_PER_DAY = 4

    # NUEVO
    MAX_KELLY_FRACTION = Decimal("0.25")  # 25% cap Kelly
    VOLATILITY_CAP = Decimal("0.50")  # Máx 50% exposición por volatilidad
    ACCOUNT_CAPITAL = Decimal("100.00")  # Capital base simulación

    def __init__(self, phase: int = 1):
        self.phase = phase
        self.daily_pnl = Decimal("0.00")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None
        self.current_day = datetime.utcnow().date()

    # ======================================================
    # NUEVO: POSITION SIZING DINÁMICO
    # ======================================================

    def compute_position_size(
        self,
        probability: Decimal,
        market_price: Decimal,
        volatility: Decimal = Decimal("0.10"),
    ) -> Decimal:
        """
        Kelly fraction sizing con caps institucionales.
        """

        probability = Decimal(str(probability))
        market_price = Decimal(str(market_price))
        volatility = Decimal(str(volatility))

        # Edge
        edge = probability - market_price

        if edge <= 0:
            return Decimal("0")

        # Kelly simplificado
        kelly_fraction = edge / (Decimal("1") - market_price)

        # Caps
        kelly_fraction = min(kelly_fraction, self.MAX_KELLY_FRACTION)

        # Volatility cap
        vol_adjustment = Decimal("1") - min(volatility, self.VOLATILITY_CAP)
        adjusted_fraction = kelly_fraction * vol_adjustment

        capital_to_risk = self.ACCOUNT_CAPITAL * adjusted_fraction

        # Cost per trade cap
        capital_to_risk = min(capital_to_risk, self.MAX_COST_PER_TRADE)

        # Convertir a size
        size = (capital_to_risk / market_price).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )

        if size <= 0:
            return Decimal("0")

        return size

    # ======================================================
    # RESTO DEL RISK MANAGER (SIN CAMBIOS)
    # ======================================================

    def validate_trade(self, size: float, price: float, icm: Decimal):
        self._auto_reset_if_new_day()
        now = datetime.utcnow()

        if self.kill_switch:
            return self._reject("Kill switch activo")

        if self._in_cooldown():
            return self._reject("Cooldown activo")

        if not self._valid_market_inputs(size, price, icm):
            return self._reject("Datos de mercado inválidos")

        size_dec = Decimal(str(size))
        price_dec = Decimal(str(price))

        if self.trade_count >= self.MAX_TRADES_PER_DAY:
            return self._reject("Límite diario de trades alcanzado")

        if icm < self.ICM_MIN:
            return self._reject("ICM insuficiente")

        if (
            self.last_trade_time
            and (now - self.last_trade_time).total_seconds()
            < self.ANTI_FOMO_MINUTES * 60
        ):
            return self._reject("Anti-FOMO activo")

        cost = size_dec * price_dec
        if cost > self.MAX_COST_PER_TRADE:
            return self._reject("Costo excede límite")

        return {"approved": True, "reason": "Trade aprobado"}

    def record_result(self, pnl: Decimal):
        self._auto_reset_if_new_day()

        pnl = Decimal(str(pnl)).quantize(Decimal("0.0001"))
        self.daily_pnl += pnl
        self.trade_count += 1
        self.last_trade_time = datetime.utcnow()

        if self.daily_pnl <= self.DAILY_LOSS_LIMIT:
            self.kill_switch = True
            return

        if pnl < 0:
            self.cooldown_until = datetime.utcnow() + timedelta(
                seconds=self.COOLDOWN_DURATION
            )

    def _auto_reset_if_new_day(self):
        today = datetime.utcnow().date()
        if today != self.current_day:
            self.reset_daily()

    def reset_daily(self):
        self.daily_pnl = Decimal("0.00")
        self.trade_count = 0
        self.kill_switch = False
        self.cooldown_until = datetime.utcnow()
        self.last_trade_time = None
        self.current_day = datetime.utcnow().date()

    def _valid_market_inputs(self, size, price, icm):
        try:
            size = Decimal(str(size))
            price = Decimal(str(price))
            icm = Decimal(str(icm))

            if size <= 0 or price <= 0:
                return False
            if icm < 0 or icm > 1:
                return False
            return True
        except (InvalidOperation, TypeError):
            return False

    def _in_cooldown(self):
        return datetime.utcnow() < self.cooldown_until

    def _reject(self, reason):
        return {"approved": False, "reason": reason}
