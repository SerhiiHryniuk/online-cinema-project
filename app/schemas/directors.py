from pydantic import BaseModel, ConfigDict, Field


class DirectorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DirectorCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
