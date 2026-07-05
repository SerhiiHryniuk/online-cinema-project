from pydantic import BaseModel, ConfigDict, Field


class GenreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class GenreWithCountSchema(BaseModel):
    id: int
    name: str
    movie_count: int


class GenreCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
