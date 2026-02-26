# tests/test_performance.py
import pytest
import time
from market_simulator import MarketSimulator

@pytest.mark.asyncio
async def test_60s_simulation_under_1s_cpu():
    """Contrato de rendimiento: 60s simulados en <1s real."""
    sim = MarketSimulator(real_time_sleep=False)
    
    start = time.time()
    await sim.run_step(60000)  # 60s simulados
    elapsed = time.time() - start
    
    assert elapsed < 1.0, f"Performance fail: {elapsed:.3f}s >= 1.0s"
    print(f"✅ 60s simulados en {elapsed:.3f}s CPU")
