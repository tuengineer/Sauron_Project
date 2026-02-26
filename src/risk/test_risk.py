# tests/test_risk.py

import pytest
import asyncio
from risk.manager import FirestoreAsyncWrapper, RiskManager, RiskException

@pytest.mark.asyncio
async def test_concurrent_budget_race_condition(monkeypatch):
    fs = FirestoreAsyncWrapper()
    rm = RiskManager(fs)

    # Inicializar estado limpio
    await rm.reset_daily_budget()

    # Ejecutar 10 coroutines con amount 1.5 USD
    amounts = [1.5]*10
    results = []

    async def attempt_trade(amount):
        try:
            await rm.validate_and_spend(amount)
            results.append(True)
        except RiskException:
            results.append(False)

    await asyncio.gather(*[attempt_trade(a) for a in amounts])

    # Verificar que el presupuesto total nunca excede $10
    state = await rm._get_state()
    assert state["used_today"] <= 10.0

    # Verificar que al menos algunos trades fueron bloqueados
    assert any(not r for r in results)

@pytest.mark.asyncio
async def test_kill_switch_blocks_trades(monkeypatch):
    fs = FirestoreAsyncWrapper()
    rm = RiskManager(fs)

    # Activar kill switch en Firestore
    async def activate_kill_switch(transaction):
        doc_ref = fs.db.collection("risk_state").document("main")
        transaction.set(doc_ref, {"kill_switch": True})
    await fs.run_transaction(activate_kill_switch)

    with pytest.raises(RiskException, match="Kill switch activo"):
        await rm.validate_and_spend(1.0)
