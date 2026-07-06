from pydantic import BaseModel, ConfigDict


class FavoriteResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
