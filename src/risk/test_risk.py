import pytest
from decimal import Decimal
from datetime import timedelta

from risk.manager import RiskManager


# ==========================================================
# 1️⃣ COSTO EXACTO LÍMITE (Boundary)
# size=5, price=0.5 → cost=2.50
# ==========================================================

def test_cost_exact_limit_approved():
    rm = RiskManager()

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.70"),
    )

    assert result["approved"] is True
    assert result["cost"] == Decimal("2.5000")
    assert rm.daily_trades == 1


# ==========================================================
# 2️⃣ COSTO EXCEDIDO
# size=6, price=0.5 → cost=3.00
# ==========================================================

def test_cost_exceeded_rejected():
    rm = RiskManager()

    result = rm.validate_trade(
        size=Decimal("6"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is False
    assert result["reason"] == "COST_EXCEEDED"


# ==========================================================
# 3️⃣ ICM BAJO
# ==========================================================

def test_icm_below_threshold_rejected():
    rm = RiskManager()

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.60"),
    )

    assert result["approved"] is False
    assert result["reason"] == "ICM_TOO_LOW"


# ==========================================================
# 4️⃣ KILL SWITCH EXACTO -6.00
# ==========================================================

def test_kill_switch_exact_boundary():
    rm = RiskManager()

    # Simular pérdida que lleva exactamente a -6.00
    rm.record_result(Decimal("-6.00"))

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is False
    assert result["reason"] == "KILL_SWITCH_ACTIVE"


# ==========================================================
# 5️⃣ COOLDOWN ACTIVO TRAS PÉRDIDA
# ==========================================================

def test_cooldown_after_single_loss():
    rm = RiskManager()

    # Registrar pérdida → activa cooldown
    rm.record_result(Decimal("-1.00"))

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is False
    assert result["reason"] == "COOLDOWN_ACTIVE"


# ==========================================================
# 6️⃣ COOLDOWN EXPIRA
# ==========================================================

def test_cooldown_expires():
    rm = RiskManager()

    rm.record_result(Decimal("-1.00"))

    # Forzar expiración manual del cooldown
    rm.cooldown_until = rm.cooldown_until - timedelta(hours=5)

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is True


# ==========================================================
# 7️⃣ MÁXIMO TRADES POR DÍA
# ==========================================================

def test_max_trades_per_day_limit():
    rm = RiskManager()

    for _ in range(4):
        rm.validate_trade(
            size=Decimal("5"),
            price=Decimal("0.5"),
            icm=Decimal("0.80"),
        )

    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is False
    assert result["reason"] == "MAX_TRADES_REACHED"


# ==========================================================
# 8️⃣ ANTI-FOMO (30 min)
# ==========================================================

def test_anti_fomo_block():
    rm = RiskManager()

    rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    # Intentar inmediatamente
    result = rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    assert result["approved"] is False
    assert result["reason"] == "ANTI_FOMO_BLOCK"


# ==========================================================
# 9️⃣ RESET DIARIO
# ==========================================================

def test_reset_daily_clears_state():
    rm = RiskManager()

    rm.record_result(Decimal("-2.00"))
    rm.validate_trade(
        size=Decimal("5"),
        price=Decimal("0.5"),
        icm=Decimal("0.80"),
    )

    rm.reset_daily()

    status = rm.get_status()

    assert status["daily_pnl"] == Decimal("0.00")
    assert status["daily_trades"] == 0
    assert status["cooldown_active"] is False
    assert status["kill_switch_active"] is False
