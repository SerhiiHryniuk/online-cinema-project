import enum
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MovieSortField(str, enum.Enum):
    PRICE = "price"
    YEAR = "year"
    IMDB = "imdb"
    VOTES = "votes"


class MovieSortOrder(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


class MovieFilterParams(BaseModel):
    year: Optional[int] = None
    min_imdb: Optional[float] = None
    max_imdb: Optional[float] = None
    search: Optional[str] = None
    sort_by: MovieSortField = MovieSortField.YEAR
    sort_order: MovieSortOrder = MovieSortOrder.DESC


class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    year: int
    imdb: float
    price: Decimal


class MovieDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Decimal
    certification_id: int


class MovieListResponseSchema(BaseModel):
    items: list[MovieListItemSchema]
    total: int
    page: int
    per_page: int
    total_pages: int
