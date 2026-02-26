import heapq
import random


class OrderBook:
    """
    L2 order book (5 niveles por lado)
    Invariante: best_bid < best_ask
    """

    def __init__(self):
        self.bids = []  # max heap (precio negativo)
        self.asks = []  # min heap
        self.depth = 5
        self._init_book()

    def _init_book(self):
        mid = 0.50
        spread = 0.01

        for i in range(self.depth):
            bid_price = round(mid - spread - i * 0.01, 4)
            ask_price = round(mid + spread + i * 0.01, 4)
            heapq.heappush(self.bids, (-bid_price, random.uniform(100, 500)))
            heapq.heappush(self.asks, (ask_price, random.uniform(100, 500)))

    def best_bid(self):
        return -self.bids[0][0]

    def best_ask(self):
        return self.asks[0][0]

    def consume_market_order(self, side: str, size: float):
        book_side = self.asks if side == "buy" else self.bids
        remaining = size

        while remaining > 0 and book_side:
            price, liquidity = heapq.heappop(book_side)
            if side == "sell":
                price = -price

            if liquidity > remaining:
                liquidity -= remaining
                remaining = 0
                if side == "buy":
                    heapq.heappush(self.asks, (price, liquidity))
                else:
                    heapq.heappush(self.bids, (-price, liquidity))
            else:
                remaining -= liquidity

        self._maintain_depth()

    def _maintain_depth(self):
        while len(self.bids) < self.depth:
            price = round(self.best_bid() - 0.01, 4)
            heapq.heappush(self.bids, (-price, random.uniform(100, 500)))

        while len(self.asks) < self.depth:
            price = round(self.best_ask() + 0.01, 4)
            heapq.heappush(self.asks, (price, random.uniform(100, 500)))

        assert self.best_bid() < self.best_ask()
