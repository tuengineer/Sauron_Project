# src/market_simulator/flow_generator.py

import random
import math
from decimal import Decimal


class VolatilityRegime:
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


REGIME_CONFIG = {
    VolatilityRegime.NORMAL: {"lambda_mult": 1.0, "informed_mult": 1.0},
    VolatilityRegime.HIGH: {"lambda_mult": 1.8, "informed_mult": 1.5},
    VolatilityRegime.EXTREME: {"lambda_mult": 3.0, "informed_mult": 2.0},
}


class FlowGenerator:
    def __init__(self, base_lambda=5):
        self.base_lambda = base_lambda
        self.base_informed_ratio = 0.15
        self.regime = VolatilityRegime.NORMAL

    def set_regime(self, regime: str):
        if regime not in REGIME_CONFIG:
            raise ValueError("Invalid volatility regime")
        self.regime = regime

    def _poisson(self, lam):
        L = math.exp(-lam)
        k = 0
        p = 1
        while p > L:
            k += 1
            p *= random.random()
        return max(0, k - 1)

    def generate_orders_for_step(self, step_ms: int):
        config = REGIME_CONFIG[self.regime]
        lam = self.base_lambda * config["lambda_mult"]
        informed_ratio = min(
            1.0,
            self.base_informed_ratio * config["informed_mult"]
        )

        arrivals = self._poisson(lam)

        orders = []

        for _ in range(arrivals):
            side = random.choice(["buy", "sell"])
            size = Decimal(random.lognormvariate(1, 0.5)).quantize(
                Decimal("0.01")
            )
            informed = random.random() < informed_ratio

            timestamp_offset = random.randint(0, step_ms)

            orders.append({
                "side": side,
                "size": size,
                "informed": informed,
                "offset_ms": timestamp_offset
            })

        orders.sort(key=lambda x: x["offset_ms"])
        return orders
