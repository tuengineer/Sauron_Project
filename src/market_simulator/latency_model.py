import random


class LatencyModel:
    """
    Base 50ms ±10ms
    Jitter 5%
    Truncado >= 1ms
    """

    def __init__(self):
        self.base = 50
        self.variance = 10
        self.jitter_pct = 0.05

    def sample(self):
        latency = random.uniform(
            self.base - self.variance,
            self.base + self.variance
        )
        jitter = latency * self.jitter_pct
        latency = random.uniform(latency - jitter, latency + jitter)
        return max(latency, 1.0)
