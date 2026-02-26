from pydantic import BaseModel


class OrderRequest(BaseModel):
    side: str
    size: float


class OrderResponse(BaseModel):
    status: str
    detail: str
