import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MovieReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: Decimal
    genre: str
    release_year: int


class CartItemCreateSchema(BaseModel):
    movie_id: int


class CartItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: int
    added_at: datetime.datetime
    movie: MovieReadSchema


class CartReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    items: list[CartItemReadSchema]
