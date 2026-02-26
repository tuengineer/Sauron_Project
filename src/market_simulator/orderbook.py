# src/market_simulator/orderbook.py

from decimal import Decimal, getcontext
from dataclasses import dataclass
from typing import List, Tuple
import heapq
import random

getcontext().prec = 28


MIN_SPREAD_BPS = Decimal("0.001")  # 10 bps = 0.1%


@dataclass(order=True)
class PriceLevel:
    price: Decimal
    size: Decimal


class OrderBookL2:
    """
    Libro L2 institucional.
    Invariante garantizado por construcción:
    best_bid < best_ask y spread >= 10 bps
    """

    def __init__(self, mid_price: Decimal = Decimal("0.50")):
        self.depth = 5
        self.mid_price = mid_price
        self.bids: List[Tuple[Decimal, Decimal]] = []
        self.asks: List[Tuple[Decimal, Decimal]] = []
        self._initialize_book()

    # ==============================
    # Inicialización estructural
    # ==============================

    def _initialize_book(self):
        base_spread = self.mid_price * MIN_SPREAD_BPS

        best_bid = self.mid_price - base_spread
        best_ask = self.mid_price + base_spread

        for i in range(self.depth):
            bid_price = best_bid - Decimal(i) * base_spread
            ask_price = best_ask + Decimal(i) * base_spread

            bid_size = Decimal(random.uniform(100, 500)).quantize(Decimal("0.01"))
            ask_size = Decimal(random.uniform(100, 500)).quantize(Decimal("0.01"))

            heapq.heappush(self.bids, (-bid_price, bid_size))
            heapq.heappush(self.asks, (ask_price, ask_size))

    # ==============================
    # Acceso seguro
    # ==============================

    def best_bid(self) -> PriceLevel:
        price, size = self.bids[0]
        return PriceLevel(price=-price, size=size)

    def best_ask(self) -> PriceLevel:
        price, size = self.asks[0]
        return PriceLevel(price=price, size=size)

    # ==============================
    # Extracción ordenada L2
    # ==============================

    def get_depth(self, levels: int = 5):
        bids_sorted = sorted(
            [PriceLevel(-p, s) for p, s in self.bids],
            reverse=True
        )[:levels]

        asks_sorted = sorted(
            [PriceLevel(p, s) for p, s in self.asks]
        )[:levels]

        return {"bids": bids_sorted, "asks": asks_sorted}

    # ==============================
    # Consumo real
    # ==============================

    def consume_market_order(self, side: str, size: Decimal):
        book_side = self.asks if side == "buy" else self.bids
        remaining = size

        while remaining > 0 and book_side:
            price, liquidity = heapq.heappop(book_side)

            if side == "sell":
                price = -price

            if liquidity > remaining:
                liquidity -= remaining
                remaining = Decimal("0")
                if side == "buy":
                    heapq.heappush(self.asks, (price, liquidity))
                else:
                    heapq.heappush(self.bids, (-price, liquidity))
            else:
                remaining -= liquidity

        self._maintain_depth()

    # ==============================
    # Reposición estructural segura
    # ==============================

    def _maintain_depth(self):
        spread_unit = self.mid_price * MIN_SPREAD_BPS

        while len(self.bids) < self.depth:
            new_price = self.best_bid().price - spread_unit
            new_size = Decimal(random.uniform(100, 500)).quantize(Decimal("0.01"))
            heapq.heappush(self.bids, (-new_price, new_size))

        while len(self.asks) < self.depth:
            new_price = self.best_ask().price + spread_unit
            new_size = Decimal(random.uniform(100, 500)).quantize(Decimal("0.01"))
            heapq.heappush(self.asks, (new_price, new_size))
