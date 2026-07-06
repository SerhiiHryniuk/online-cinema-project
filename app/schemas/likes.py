from pydantic import BaseModel, ConfigDict

from app.models.interactions import LikeType


class LikeRequestSchema(BaseModel):
    type: LikeType


class LikeResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
    type: LikeType


class MovieLikesCountSchema(BaseModel):
    likes: int
    dislikes: int
