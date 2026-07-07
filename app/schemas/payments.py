from datetime import datetime
from typing import Annotated, List, Optional
from pydantic import BaseModel, ConfigDict, Field


PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class CheckoutRequestSchema(BaseModel):
    order_id: PositiveInt


class CheckoutResponseSchema(BaseModel):
    checkout_url: str
    session_id: str


class PaymentItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    price: NonNegativeFloat


class PaymentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    amount: NonNegativeFloat
    status: str
    external_payment_id: Optional[str] = None
    created_at: datetime
    items: List[PaymentItemResponseSchema] = Field(default_factory=list)


class PaymentHistoryFilterSchema(BaseModel):
    status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0)] = 0


class AdminPaymentFilterSchema(BaseModel):
    user_id: Optional[PositiveInt] = None
    status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0)] = 0
