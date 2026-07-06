import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class GenreReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MovieReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: Decimal
    genres: list[GenreReadSchema]
    year: int


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
