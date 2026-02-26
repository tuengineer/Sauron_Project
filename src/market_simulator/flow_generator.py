import random
import math


class FlowGenerator:
    """
    Poisson arrivals
    Log-normal size
    15% informed traders
    """

    def __init__(self, lambda_rate=5):
        self.lambda_rate = lambda_rate
        self.informed_ratio = 0.15

    def poisson_arrivals(self):
        L = math.exp(-self.lambda_rate)
        k = 0
        p = 1
        while p > L:
            k += 1
            p *= random.random()
        return k - 1

    def generate_order(self):
        side = random.choice(["buy", "sell"])
        size = random.lognormvariate(1, 0.5)
        informed = random.random() < self.informed_ratio
        return {
            "side": side,
            "size": size,
            "informed": informed
        }
