from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class MovieCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    year: int = Field(ge=1888, le=2100)
    time: int = Field(ge=1)
    imdb: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)
    meta_score: Optional[float] = Field(default=None, ge=0, le=100)
    gross: Optional[float] = Field(default=None, ge=0)
    description: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    certification_id: int
    genre_ids: list[int] = []
    star_ids: list[int] = []
    director_ids: list[int] = []


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    year: Optional[int] = Field(default=None, ge=1888, le=2100)
    time: Optional[int] = Field(default=None, ge=1)
    imdb: Optional[float] = Field(default=None, ge=0, le=10)
    votes: Optional[int] = Field(default=None, ge=0)
    meta_score: Optional[float] = Field(default=None, ge=0, le=100)
    gross: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, min_length=1)
    price: Optional[Decimal] = Field(default=None, ge=0)
    certification_id: Optional[int] = None
    genre_ids: Optional[list[int]] = None
    star_ids: Optional[list[int]] = None
    director_ids: Optional[list[int]] = None
