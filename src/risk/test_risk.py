# src/risk/test_risk.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from src.risk.manager import RiskManager

# ==============================
# FIXTURES
# ==============================
@pytest.fixture
def risk_manager():
    return RiskManager()

# ==============================
# 1. VALIDACIÓN BÁSICA
# ==============================
def test_trade_approved(risk_manager):
    icm = Decimal("0.75")
    result = risk_manager.validate_trade(size=1.0, price=1.0, icm=icm)
    assert result["approved"] is True

def test_trade_rejected_icm_low(risk_manager):
    icm = Decimal("0.65")
    result = risk_manager.validate_trade(size=1.0, price=1.0, icm=icm)
    assert result["approved"] is False
    assert "ICM" in result["reason"]

def test_trade_rejected_cost_high(risk_manager):
    icm = Decimal("0.75")
    result = risk_manager.validate_trade(size=2.0, price=2.0, icm=icm)
    assert result["approved"] is False
    assert "Costo" in result["reason"]

def test_trade_rejected_max_trades(risk_manager):
    icm = Decimal("0.75")
    # Simular 4 trades ya ejecutados
    for _ in range(risk_manager.MAX_TRADES_PER_DAY):
        risk_manager.trade_count += 1
    result = risk_manager.validate_trade(size=1.0, price=1.0, icm=icm)
    assert result["approved"] is False
    assert "Límite diario" in result["reason"]

def test_trade_rejected_anti_fomo(risk_manager):
    icm = Decimal("0.75")
    risk_manager.last_trade_time = datetime.utcnow()
    result = risk_manager.validate_trade(size=1.0, price=1.0, icm=icm)
    assert result["approved"] is False
    assert "Anti-FOMO" in result["reason"]

# ==============================
# 2. COOLDOWN Y KILL SWITCH
# ==============================
def test_cooldown_activates_on_loss(risk_manager):
    risk_manager.record_result(Decimal("-1.00"))
    assert risk_manager.cooldown_until > datetime.utcnow()
    assert risk_manager.kill_switch is False

def test_kill_switch_activates_on_limit(risk_manager):
    # Forzar daily_pnl cercano al límite
    risk_manager.daily_pnl = Decimal("-5.50")
    risk_manager.record_result(Decimal("-1.00"))
    assert risk_manager.kill_switch is True

def test_no_trade_during_cooldown(risk_manager):
    risk_manager.record_result(Decimal("-1.00"))
    assert not risk_manager.can_trade()  # Cooldown activo

def test_no_trade_after_kill_switch(risk_manager):
    risk_manager.daily_pnl = Decimal("-6.00")
    risk_manager.record_result(Decimal("0"))
    assert not risk_manager.can_trade()
    assert risk_manager.kill_switch is True

# ==============================
# 3. RESET Y MANUAL
# ==============================

def test_reset_daily_clears_all(risk_manager):
    risk_manager.daily_pnl = Decimal("-2.00")
    risk_manager.trade_count = 3
    risk_manager.kill_switch = True
    risk_manager.cooldown_until = datetime.utcnow() + timedelta(hours=1)

    risk_manager.reset_daily()

    assert risk_manager.daily_pnl == Decimal("0.0")
    assert risk_manager.trade_count == 0
    assert risk_manager.kill_switch is False
    assert risk_manager.last_trade_time is None


def test_force_kill_switch_manual(risk_manager):
    risk_manager.force_kill_switch()
    assert risk_manager.kill_switch is True
    assert risk_manager.daily_pnl == risk_manager.DAILY_LOSS_LIMIT


def test_manual_reset_restores_trading(risk_manager):
    risk_manager.force_kill_switch()
    risk_manager.manual_reset()
    assert risk_manager.kill_switch is False
    assert risk_manager.can_trade() is True


# ==============================
# 4. SECUENCIAS
# ==============================

def test_sequence_two_losses_cooldown(risk_manager):
    risk_manager.record_result(Decimal("-1.00"))
    first_cooldown = risk_manager.cooldown_until

    risk_manager.cooldown_until = datetime.utcnow()  # Forzar fin cooldown
    risk_manager.record_result(Decimal("-0.50"))

    assert risk_manager.cooldown_until > first_cooldown


def test_sequence_accumulated_loss_kill_switch(risk_manager):
    risk_manager.record_result(Decimal("-3.00"))
    risk_manager.cooldown_until = datetime.utcnow()
    risk_manager.record_result(Decimal("-3.50"))

    assert risk_manager.kill_switch is True


def test_sequence_successful_day(risk_manager):
    risk_manager.record_result(Decimal("1.00"))
    risk_manager.record_result(Decimal("0.50"))

    assert risk_manager.kill_switch is False
    assert risk_manager.daily_pnl == Decimal("1.50")


# ==============================
# 5. AUDITOR EDGE CASES
# ==============================

# --- Precisión Decimal ---
def test_decimal_precision_not_float_sensitive(risk_manager):
    risk_manager.record_result(Decimal("-1.3333"))
    risk_manager.cooldown_until = datetime.utcnow()
    risk_manager.record_result(Decimal("-4.6667"))

    # Exactamente -6.0000
    assert risk_manager.daily_pnl == Decimal("-6.0000")
    assert risk_manager.kill_switch is True


# --- Persistencia de estado (simulada) ---
def test_state_persistence_simulation():
    rm1 = RiskManager()
    rm1.record_result(Decimal("-2.00"))

    # Simular "reinicio" copiando estado
    rm2 = RiskManager()
    rm2.daily_pnl = rm1.daily_pnl
    rm2.trade_count = rm1.trade_count
    rm2.kill_switch = rm1.kill_switch
    rm2.cooldown_until = rm1.cooldown_until

    assert rm2.daily_pnl == Decimal("-2.00")
    assert rm2.trade_count == 1


# --- Datos de mercado corruptos ---
def test_invalid_market_data_rejected(risk_manager):
    icm = Decimal("0.75")

    # size negativo
    result = risk_manager.validate_trade(size=-1.0, price=1.0, icm=icm)
    assert result["approved"] is False

    # price negativo
    result = risk_manager.validate_trade(size=1.0, price=-1.0, icm=icm)
    assert result["approved"] is False


# --- Cambio de día UTC ---
def test_exact_utc_day_change_resets_properly(risk_manager):
    risk_manager.record_result(Decimal("-2.00"))

    # Simular cambio de día manual
    risk_manager.reset_daily()

    assert risk_manager.daily_pnl == Decimal("0.0")
    assert risk_manager.trade_count == 0
    assert risk_manager.kill_switch is False
