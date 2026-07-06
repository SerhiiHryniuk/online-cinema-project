from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentCreateSchema(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: Optional[int] = None


class ReplySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
    parent_id: Optional[int] = None
    content: str
    created_at: datetime


class CommentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    movie_id: int
    parent_id: Optional[int] = None
    content: str
    created_at: datetime
    replies: list[ReplySchema] = []


class NotificationResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    comment_id: Optional[int] = None
    type: str
    message: str
    is_read: bool
    created_at: datetime
