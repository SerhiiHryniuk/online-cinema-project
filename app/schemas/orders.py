from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OrderItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: int
    price_at_order: Decimal


class OrderCreateSchema(BaseModel):
    pass


class OrderResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    status: str
    total_amount: Optional[Decimal] = None


class OrderDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    status: str
    total_amount: Optional[Decimal] = None
    items: list[OrderItemSchema]


class OrderListResponseSchema(BaseModel):
    items: list[OrderResponseSchema]
    total: int
    page: int
    per_page: int
    total_pages: int


class OrderFilterParamsSchema(BaseModel):
    user_id: Optional[int] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    per_page: int = 10


class OrderCancelRequestSchema(BaseModel):
    reason: Optional[str] = None
