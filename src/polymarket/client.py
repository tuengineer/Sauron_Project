class PolymarketSimulatorClient:
    def __init__(self, simulator, risk_manager=None):
        self.simulator = simulator
        self.risk_manager = risk_manager

    async def health(self):
        return {"status": "ok"}

    async def place_order(self, order):
        if self.risk_manager:
            allowed = self.risk_manager.check(order.size)
            if not allowed:
                return {"status": "blocked"}

        await self.simulator.step()
        return {"status": "filled"}

    async def get_book(self):
        return {
            "bid": self.simulator.book.best_bid(),
            "ask": self.simulator.book.best_ask()
        }

    async def run_simulation(self, steps: int):
        await self.simulator.run(steps)
        return {"status": "completed"}

    async def reset(self):
        self.simulator = type(self.simulator)(
            real_time_sleep=self.simulator.real_time_sleep
        )
        return {"status": "reset"}
