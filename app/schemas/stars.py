from pydantic import BaseModel, ConfigDict, Field


class StarSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StarCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
