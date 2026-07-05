from pydantic import BaseModel, ConfigDict


class GenreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class GenreWithCountSchema(BaseModel):
    id: int
    name: str
    movie_count: int
