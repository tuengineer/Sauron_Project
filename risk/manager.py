# risk/manager.py

import os
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from google.cloud import firestore

class RiskException(Exception):
    pass

class FirestoreAsyncWrapper:
    """Wrapper de Firestore con ThreadPoolExecutor para async"""
    def __init__(self, project_id=None):
        from concurrent.futures import ThreadPoolExecutor
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.db = firestore.Client(project=self.project_id)
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def run_transaction(self, func):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, lambda: self.db.run_transaction(func))

    async def get_document(self, collection: str, doc_id: str):
        loop = asyncio.get_event_loop()
        def _get():
            doc = self.db.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        return await loop.run_in_executor(self.executor, _get)

class RiskManager:
    DAILY_BUDGET = Decimal("10.00")
    MAX_PER_TRADE = Decimal("2.00")
    MAX_POSITIONS = 5
    COOLDOWN_HOURS = 4

    def __init__(self, fs: FirestoreAsyncWrapper):
        self.fs = fs

    # -------------------------------
    # MÉTODO PRIVADO: obtener o inicializar estado
    # -------------------------------
    def _normalize_amount(self, amount: float) -> Decimal:
        d = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if d > self.MAX_PER_TRADE:
            raise RiskException(f"Monto por trade excede {self.MAX_PER_TRADE} USD")
        return d

    def _get_default_state(self):
        now = datetime.utcnow()
        return {
            "kill_switch": False,
            "used_today": Decimal("0.00"),
            "open_positions": 0,
            "consecutive_losses": 0,
            "cooldown_until": None,
            "last_reset": now.date().isoformat()
        }

    async def _get_state(self):
        doc = await self.fs.get_document("risk_state", "main")
        if doc:
            # Convert used_today a Decimal si viene como float
            doc["used_today"] = Decimal(str(doc.get("used_today", "0.00")))
            return doc
        return self._get_default_state()

    # -------------------------------
    # VALIDAR Y GASTAR PRESUPUESTO (TRANSACCIÓN ATÓMICA)
    # -------------------------------
    async def validate_and_spend(self, amount: float):
        amount = self._normalize_amount(amount)

        async def transaction_logic(transaction):
            doc_ref = self.fs.db.collection("risk_state").document("main")
            snapshot = doc_ref.get(transaction=transaction)
            now = datetime.utcnow()

            if snapshot.exists:
                state = snapshot.to_dict()
                state["used_today"] = Decimal(str(state.get("used_today", "0.00")))
            else:
                state = self._get_default_state()

            # 1. Kill switch
            if state.get("kill_switch", False):
                raise RiskException("Kill switch activo")

            # 2. Cooldown
            cooldown_until = state.get("cooldown_until")
            if cooldown_until:
                cooldown_dt = datetime.fromisoformat(cooldown_until)
                if now < cooldown_dt:
                    raise RiskException(f"Cooldown activo hasta {cooldown_until}")

            # 3. Max posiciones
            if state.get("open_positions", 0) >= self.MAX_POSITIONS:
                raise RiskException("Número máximo de posiciones alcanzado")

            # 4. Budget diario
            if state.get("used_today", Decimal("0.00")) + amount > self.DAILY_BUDGET:
                raise RiskException(f"Presupuesto diario excedido: {state.get('used_today') + amount} > {self.DAILY_BUDGET}")

            # 5. Actualizar estado de manera atómica
            state["used_today"] += amount
            state["open_positions"] = state.get("open_positions", 0) + 1

            # Convertir a float para Firestore
            state["used_today"] = float(state["used_today"])

            transaction.set(doc_ref, state)
            return state

        return await self.fs.run_transaction(transaction_logic)

    # -------------------------------
    # CERRAR POSICIÓN
    # -------------------------------
    async def close_position(self, profit_loss: float):
        async def transaction_logic(transaction):
            doc_ref = self.fs.db.collection("risk_state").document("main")
            snapshot = doc_ref.get(transaction=transaction)
            now = datetime.utcnow()

            if snapshot.exists:
                state = snapshot.to_dict()
                state["used_today"] = Decimal(str(state.get("used_today", "0.00")))
            else:
                state = self._get_default_state()

            # Decrementar posiciones abiertas
            state["open_positions"] = max(0, state.get("open_positions", 0) - 1)

            # Actualizar streak de pérdidas y cooldown
            if profit_loss < 0:
                state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
                if state["consecutive_losses"] >= 3:
                    state["cooldown_until"] = (now + timedelta(hours=self.COOLDOWN_HOURS)).isoformat()
                    state["consecutive_losses"] = 0
            else:
                state["consecutive_losses"] = 0

            transaction.set(doc_ref, state)
            return state

        await self.fs.run_transaction(transaction_logic)

    # -------------------------------
    # RESET DIARIO
    # -------------------------------
    async def reset_daily_budget(self):
        """Llamado por Cloud Scheduler a las 00:00 UTC"""
        async def transaction_logic(transaction):
            doc_ref = self.fs.db.collection("risk_state").document("main")
            snapshot = doc_ref.get(transaction=transaction)

            if snapshot.exists:
                state = snapshot.to_dict()
                state["used_today"] = 0.0
                state["consecutive_losses"] = 0
                state["open_positions"] = 0
                state["cooldown_until"] = None
                state["last_reset"] = datetime.utcnow().date().isoformat()
                transaction.set(doc_ref, state)
                return True
            return False

        return await self.fs.run_transaction(transaction_logic)
