from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import logging
from datetime import datetime

from risk.manager import FirestoreAsyncWrapper, RiskManager

app = FastAPI(title="Sauron v2", version="2.0.0")

# Logging estructurado JSON para Cloud Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Inicialización lazy
_fs = None
_rm = None

async def get_risk_manager():
    global _fs, _rm
    if _fs is None:
        _fs = FirestoreAsyncWrapper()
        _rm = RiskManager(_fs)
    return _rm

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sauron-v2"}

@app.post("/scan")
async def scan(rm: RiskManager = Depends(get_risk_manager)):
    """
    Ciclo de trading:
    1. Fetch oportunidades (placeholder)
    2. Validar riesgo
    3. Ejecutar si aprobado
    4. Notificar Discord
    """
    # TODO: Implementar lógica de trading
    logging.info("Scan iniciado")
    return {"scanned": 0, "executed": 0}

@app.post("/reset")
async def reset(rm: RiskManager = Depends(get_risk_manager)):
    """Reset diario de budget - llamado por Cloud Scheduler"""
    result = await rm.reset_daily_budget()
    logging.info(f"Reset diario ejecutado: {result}")
    return {"reset": result}

@app.post("/kill-switch")
async def kill_switch(active: bool, rm: RiskManager = Depends(get_risk_manager)):
    """Activar/desactivar kill switch manualmente"""
    # TODO: Actualizar Firestore directamente
    logging.warning(f"Kill switch actualizado manualmente: {active}")
    return {"kill_switch": active}

@app.get("/status")
async def status(rm: RiskManager = Depends(get_risk_manager)):
    """Estado completo del sistema"""
    state = await rm._get_state()
    return {
        "kill_switch": state.get("kill_switch"),
        "used_today": state.get("used_today"),
        "open_positions": state.get("open_positions"),
        "cooldown_until": state.get("cooldown_until")
    }
