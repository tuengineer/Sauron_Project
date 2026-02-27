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
