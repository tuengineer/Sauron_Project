from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

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

# -------------------------------
# Middleware global de seguridad
# -------------------------------
@app.middleware("http")
async def kill_switch_middleware(request: Request, call_next):
    """
    Bloquea TODAS las operaciones si kill switch activo.
    Solo permite: health, kill-switch, status
    """
    exempt_paths = {"/health", "/kill-switch", "/status", "/docs", "/openapi.json"}

    if request.url.path not in exempt_paths:
        try:
            rm = await get_risk_manager()
            state = await rm._get_state()
            if state.get("kill_switch"):
                logging.warning(f"🔒 Request bloqueada por kill switch: {request.url.path}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Kill switch activo",
                        "kill_switch": True,
                        "retry_after": "manual"
                    }
                )
        except Exception as e:
            logging.error(f"Error leyendo estado para kill switch check: {e}")
            return JSONResponse(
                status_code=503,
                content={"error": "No se puede verificar estado de seguridad"}
            )

    return await call_next(request)

# -------------------------------
# Endpoints
# -------------------------------
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
    logging.info("Scan iniciado")
    # TODO: Implementar lógica de trading
    return {"scanned": 0, "executed": 0}

@app.post("/reset")
async def reset(rm: RiskManager = Depends(get_risk_manager)):
    """Reset diario de budget - llamado por Cloud Scheduler"""
    result = await rm.reset_daily_budget()
    logging.info(f"Reset diario ejecutado: {result}")
    return {"reset": result}

@app.post("/kill-switch")
async def kill_switch(active: bool, rm: RiskManager = Depends(get_risk_manager)):
    """
    Activar/desactivar kill switch manualmente.
    CRÍTICO: Persiste en Firestore, no solo log.
    """
    async def transaction_logic(transaction):
        doc_ref = rm.fs.db.collection("risk_state").document("main")
        snapshot = doc_ref.get(transaction=transaction)

        if snapshot.exists:
            state = snapshot.to_dict()
        else:
            state = rm._get_default_state()

        previous = state.get("kill_switch", False)
        state["kill_switch"] = active
        state["kill_switch_updated_at"] = datetime.utcnow().isoformat()
        state["kill_switch_updated_by"] = "manual_api"

        transaction.set(doc_ref, state)
        return {"previous": previous, "current": active}

    try:
        result = await rm.fs.run_transaction(transaction_logic)
        status = "ACTIVADO" if active else "DESACTIVADO"
        logging.critical(f"🚨 KILL SWITCH {status} | Antes: {result['previous']} → Ahora: {result['current']}")

        return {
            "kill_switch": active,
            "previous": result["previous"],
            "timestamp": datetime.utcnow().isoformat(),
            "persisted": True
        }
    except Exception as e:
        logging.error(f"❌ Fallo kill switch: {e}")
        raise HTTPException(status_code=500, detail=f"Kill switch failed: {str(e)}")

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
