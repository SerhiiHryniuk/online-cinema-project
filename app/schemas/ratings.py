from pydantic import BaseModel, ConfigDict, Field


class RatingRequestSchema(BaseModel):
    score: int = Field(ge=1, le=10)


class RatingResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
    score: int


class MovieRatingSummarySchema(BaseModel):
    average: float
    count: int
