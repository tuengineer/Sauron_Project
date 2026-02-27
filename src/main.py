"""
Sauron v2 — FastAPI institucional.
Integración limpia con RiskManager v2.0 (en memoria).
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional
from datetime import datetime
import asyncio
import logging
import time

from risk.manager import RiskManager  # ← NUEVA versión v2.0
from market_simulator import MarketSimulator
from polymarket import PolymarketSimulatorClient, Order, PolymarketClientError

# =====================================================
# Logging
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sauron")

# =====================================================
# Contexto global
# =====================================================

_simulator: Optional[MarketSimulator] = None
_client: Optional[PolymarketSimulatorClient] = None
_risk_manager: Optional[RiskManager] = None
_simulation_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulator, _client, _risk_manager

    _simulator = MarketSimulator(real_time_sleep=False)
    _risk_manager = RiskManager(phase=1)  # ← NUEVO
    _client = PolymarketSimulatorClient(_simulator)

    logger.info("Sauron v2 iniciado (RiskManager v2.0)")
    yield

    if _simulation_task:
        _simulation_task.cancel()

    logger.info("Sauron v2 detenido")


app = FastAPI(
    title="Sauron v2",
    version="2.1.0",
    description="Simulador institucional con RiskManager v2.0",
    lifespan=lifespan
)

# =====================================================
# Dependencias
# =====================================================

def get_simulator() -> MarketSimulator:
    if _simulator is None:
        raise HTTPException(status_code=503, detail="Simulador no inicializado")
    return _simulator


def get_client() -> PolymarketSimulatorClient:
    if _client is None:
        raise HTTPException(status_code=503, detail="Cliente no inicializado")
    return _client


def get_risk_manager() -> RiskManager:
    if _risk_manager is None:
        raise HTTPException(status_code=503, detail="RiskManager no inicializado")
    return _risk_manager


# =====================================================
# Middleware Kill Switch
# =====================================================

@app.middleware("http")
async def kill_switch_middleware(request, call_next):
    exempt_paths = {"/health", "/kill-switch", "/status", "/docs", "/openapi.json"}
    if request.url.path not in exempt_paths:
        rm = get_risk_manager()
        status = rm.get_status()

        if status["kill_switch_active"]:
            return JSONResponse(
                status_code=503,
                content={"error": "Kill switch activo"}
            )

    return await call_next(request)


# =====================================================
# Endpoints Sistema
# =====================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "sauron-v2",
        "risk_manager_version": "2.0",
        "simulation_running": _simulation_task is not None and not _simulation_task.done()
    }


@app.post("/kill-switch")
async def kill_switch(active: bool, rm: RiskManager = Depends(get_risk_manager)):
    if active:
        rm.force_kill_switch()   # ← Método recomendado en v2.0
        logger.critical("🚨 KILL SWITCH ACTIVADO")
    else:
        rm.manual_reset()        # ← Reset limpio
        logger.info("Kill switch desactivado manualmente")

    return {
        "kill_switch": active,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/status")
async def status(rm: RiskManager = Depends(get_risk_manager)):
    return rm.get_status()


# =====================================================
# Simulación
# =====================================================

@app.post("/simulate/start")
async def simulate_start(client: PolymarketSimulatorClient = Depends(get_client)):
    global _simulation_task

    if _simulation_task and not _simulation_task.done():
        return {"status": "already_running"}

    async def simulation_loop():
        while True:
            try:
                await client.sim.run_step(60000)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en simulación: {e}")
                await asyncio.sleep(1)

    _simulation_task = asyncio.create_task(simulation_loop())
    return {"status": "started"}


@app.post("/simulate/stop")
async def simulate_stop():
    global _simulation_task

    if _simulation_task:
        _simulation_task.cancel()
        try:
            await _simulation_task
        except asyncio.CancelledError:
            pass
        _simulation_task = None

    return {"status": "stopped"}


# =====================================================
# Trade con validación explícita de riesgo
# =====================================================

@app.post("/simulate/trade")
async def simulate_trade(
    market_id: str = Query(...),
    side: str = Query(..., regex="^(YES|NO)$"),
    size: float = Query(..., gt=0),
    price: float = Query(..., gt=0, lt=1),
    icm: float = Query(default=0.75, ge=0, le=1),
    rm: RiskManager = Depends(get_risk_manager),
    client: PolymarketSimulatorClient = Depends(get_client)
):
    size_d = Decimal(str(size))
    price_d = Decimal(str(price))
    icm_d = Decimal(str(icm))

    # 1️⃣ VALIDACIÓN DE RIESGO
    validation = rm.validate_trade(
        size=size_d,
        price=price_d,
        icm=icm_d
    )

    if not validation["approved"]:
        raise HTTPException(
            status_code=403,
            detail={
                "rejected": True,
                "reason": validation["reason"],
                "cost": float(validation["cost"])
            }
        )

    # 2️⃣ EJECUCIÓN
    order = Order(
        market_id=market_id,
        side=side,
        size=size_d,
        price=price_d
    )

    try:
        result = await client.place_order(order)

        # 3️⃣ REGISTRAR RESULTADO (PnL simulado)
        pnl = result.realized_pnl if hasattr(result, "realized_pnl") else Decimal("0")
        rm.record_result(Decimal(str(pnl)))

        return {
            "order": {
                "market_id": result.market_id,
                "side": result.side,
                "size_filled": float(result.filled_size),
                "price_executed": float(result.executed_price) if result.executed_price else None,
                "status": result.status,
                "latency_ms": result.latency_ms
            },
            "risk_status": rm.get_status()
        }

    except PolymarketClientError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =====================================================
# Backtest
# =====================================================

@app.post("/backtest/run")
async def backtest_run(
    duration_minutes: int = Query(default=60, ge=1, le=1440),
    regime: str = Query(default="NORMAL", regex="^(NORMAL|HIGH|EXTREME)$"),
    sim: MarketSimulator = Depends(get_simulator)
):
    sim.trade_history = []
    sim.current_time_ms = 0
    sim.set_volatility_regime(regime)

    start_real = time.time()

    for _ in range(duration_minutes):
        await sim.run_step(60000)

    elapsed_real = time.time() - start_real

    return {
        "duration_minutes": duration_minutes,
        "regime": regime,
        "speedup": round((duration_minutes * 60) / elapsed_real, 1)
        if elapsed_real > 0 else 0,
        "results": sim.get_simulation_stats()
    }
