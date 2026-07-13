from pydantic import BaseModel, ConfigDict, Field


class CertificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CertificationCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=50)
