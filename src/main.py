"""
Sauron v2 — FastAPI institucional.
Integra: RiskManager, MarketSimulator, PolymarketClient.
"""

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
import time

from risk.manager import FirestoreAsyncWrapper, RiskManager, RiskException
from market_simulator import MarketSimulator
from polymarket import PolymarketSimulatorClient, Order, PolymarketClientError

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sauron")

# =====================================================
# Contexto global de la app
# =====================================================
_simulator: Optional[MarketSimulator] = None
_client: Optional[PolymarketSimulatorClient] = None
_risk_manager: Optional[RiskManager] = None
_simulation_task: Optional[asyncio.Task] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown de recursos."""
    global _simulator, _client, _risk_manager

    _simulator = MarketSimulator(real_time_sleep=False)
    _risk_manager = RiskManager(FirestoreAsyncWrapper())
    _client = PolymarketSimulatorClient(_simulator, _risk_manager)

    logger.info("Sauron v2 iniciado")
    yield
    if _simulation_task:
        _simulation_task.cancel()
    logger.info("Sauron v2 detenido")

app = FastAPI(
    title="Sauron v2",
    version="2.0.0",
    description="Simulador institucional de microestructura de mercado",
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
# Middleware: Kill Switch Global
# =====================================================
@app.middleware("http")
async def kill_switch_middleware(request, call_next):
    exempt_paths = {"/health", "/kill-switch", "/status", "/docs", "/openapi.json"}
    if request.url.path not in exempt_paths:
        try:
            rm = get_risk_manager()
            state = await rm._get_state()
            if state.get("kill_switch"):
                return JSONResponse(
                    status_code=503,
                    content={"error": "Kill switch activo", "retry_after": "manual"}
                )
        except Exception as e:
            logger.error(f"Error verificando kill switch: {e}")
            return JSONResponse(
                status_code=503,
                content={"error": "No se puede verificar estado de seguridad"}
            )
    return await call_next(request)

# =====================================================
# Endpoints 1-3: Sistema y control
# =====================================================
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "sauron-v2",
        "mode": "simulator",
        "simulation_running": _simulation_task is not None and not _simulation_task.done()
    }

@app.post("/kill-switch")
async def kill_switch(active: bool, rm: RiskManager = Depends(get_risk_manager)):
    try:
        async def transaction_logic(transaction):
            from google.cloud import firestore
            doc_ref = rm.fs.db.collection("risk_state").document("main")
            snapshot = doc_ref.get(transaction=transaction)
            state = snapshot.to_dict() if snapshot.exists else rm._get_default_state()
            previous = state.get("kill_switch", False)
            state["kill_switch"] = active
            state["kill_switch_updated_at"] = datetime.utcnow().isoformat()
            state["kill_switch_updated_by"] = "api_manual"
            transaction.set(doc_ref, state)
            return {"previous": previous, "current": active}

        result = await rm.fs.run_transaction(transaction_logic)
        status = "ACTIVADO" if active else "DESACTIVADO"
        logger.critical(f"🚨 KILL SWITCH {status}")
        return {
            "kill_switch": active,
            "previous": result["previous"],
            "timestamp": datetime.utcnow().isoformat(),
            "persisted": True
        }
    except Exception as e:
        logger.error(f"Error kill switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status(rm: RiskManager = Depends(get_risk_manager)):
    state = await rm._get_state()
    return {
        "kill_switch": state.get("kill_switch"),
        "used_today": float(state.get("used_today", 0)),
        "open_positions": state.get("open_positions"),
        "consecutive_losses": state.get("consecutive_losses"),
        "cooldown_until": state.get("cooldown_until"),
        "last_reset": state.get("last_reset")
    }

# =====================================================
# Endpoints 4-9: Simulación
# =====================================================
@app.post("/simulate/start")
async def simulate_start(background_tasks: BackgroundTasks, client: PolymarketSimulatorClient = Depends(get_client)):
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
    return {"status": "started", "market": "sim-1"}

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

@app.post("/simulate/regime/{market_id}")
async def simulate_regime(
    market_id: str,
    regime: str = Query(..., regex="^(NORMAL|HIGH|EXTREME)$"),
    sim: MarketSimulator = Depends(get_simulator)
):
    try:
        sim.set_volatility_regime(regime)
        return {
            "market": market_id,
            "regime": regime,
            "status": "updated",
            "timestamp_ms": sim.current_time_ms
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/simulate/quote/{market_id}")
async def simulate_quote(market_id: str, client: PolymarketSimulatorClient = Depends(get_client)):
    try:
        book = await client.get_orderbook(market_id)
        return {
            "market_id": market_id,
            "bid": float(book.bids[0].price) if book.bids else None,
            "ask": float(book.asks[0].price) if book.asks else None,
            "spread_bps": float(
                (book.asks[0].price - book.bids[0].price) /
                ((book.asks[0].price + book.bids[0].price) / 2) * 10000
            ) if book.bids and book.asks else None,
            "timestamp_ms": book.timestamp_ms
        }
    except PolymarketClientError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/simulate/stats/{market_id}")
async def simulate_stats(market_id: str, client: PolymarketSimulatorClient = Depends(get_client)):
    stats = client.get_simulator_stats(market_id)
    return {
        "market_id": market_id,
        "stats": stats
    }

@app.post("/simulate/trade")
async def simulate_trade(
    market_id: str = Query(...),
    side: str = Query(..., regex="^(YES|NO)$"),
    size: float = Query(..., gt=0),
    price: float = Query(..., gt=0, lt=1),
    client: PolymarketSimulatorClient = Depends(get_client)
):
    order = Order(
        market_id=market_id,
        side=side,
        size=Decimal(str(size)),
        price=Decimal(str(price))
    )
    try:
        result = await client.place_order(order)
        return {
            "order": {
                "market_id": result.market_id,
                "side": result.side,
                "size_requested": float(size),
                "size_filled": float(result.filled_size),
                "price_executed": float(result.executed_price) if result.executed_price else None,
                "slippage_bps": float(result.slippage * 10000) if result.slippage else None,
                "status": result.status,
                "latency_ms": result.latency_ms
            }
        }
    except PolymarketClientError as e:
        raise HTTPException(status_code=403, detail=str(e))

# =====================================================
# Endpoint 10: Backtest
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
        "backtest_config": {
            "duration_minutes": duration_minutes,
            "regime": regime,
            "steps_executed": duration_minutes
        },
        "performance": {
            "real_time_seconds": round(elapsed_real, 3),
            "simulated_time_seconds": duration_minutes * 60,
            "speedup": round((duration_minutes * 60) / elapsed_real, 1) if elapsed_real > 0 else 0
        },
        "results": sim.get_simulation_stats()
    }
