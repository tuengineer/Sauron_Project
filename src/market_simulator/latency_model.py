# src/market_simulator/latency_model.py

import random


class LatencyModel:
    """
    Latencia institucional:
    Base 50±10ms
    Floor 20ms
    Hard cap 150ms
    5% spike adicional 50–200ms
    """

    def __init__(self):
        self.base = 50
        self.variance = 10
        self.floor = 20
        self.cap = 150
        self.spike_probability = 0.05

    def sample(self) -> float:
        latency = random.uniform(
            self.base - self.variance,
            self.base + self.variance
        )

        if random.random() < self.spike_probability:
            latency += random.uniform(50, 200)

        latency = max(self.floor, latency)
        latency = min(self.cap, latency)

        return latency
