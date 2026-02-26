import asyncio
from .orderbook import OrderBook
from .latency_model import LatencyModel
from .flow_generator import FlowGenerator


class MarketSimulator:
    def __init__(self, real_time_sleep: bool = False):
        self.real_time_sleep = real_time_sleep
        self.book = OrderBook()
        self.latency = LatencyModel()
        self.flow = FlowGenerator()

    async def step(self):
        orders = self.flow.poisson_arrivals()

        for _ in range(orders):
            order = self.flow.generate_order()
            self.book.consume_market_order(order["side"], order["size"])

        latency_ms = self.latency.sample()

        if self.real_time_sleep:
            await asyncio.sleep(latency_ms / 1000.0)

    async def run(self, steps: int):
        for _ in range(steps):
            await self.step()
