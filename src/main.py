from fastapi import FastAPI
from market_simulator import MarketSimulator
from polymarket.client import PolymarketSimulatorClient

app = FastAPI()

simulator = MarketSimulator(real_time_sleep=False)
client = PolymarketSimulatorClient(simulator)


@app.get("/health")
async def health():
    return await client.health()


@app.post("/order")
async def order(order: dict):
    return await client.place_order(order)


@app.get("/book")
async def book():
    return await client.get_book()


@app.post("/run/{steps}")
async def run(steps: int):
    return await client.run_simulation(steps)


@app.post("/reset")
async def reset():
    return await client.reset()
