from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.comments import (
    create_comment,
    get_comment_by_id,
    get_movie_comments,
)
from app.crud.movies import get_movie_by_id
from app.db.session import get_db
from app.models.accounts import User
from app.schemas.comments import (
    CommentCreateSchema,
    CommentResponseSchema,
)

router = APIRouter()


@router.post(
    "/{movie_id}/comments/",
    response_model=CommentResponseSchema,
    summary="Create a Comment",
    description=(
        "Create a comment on a movie, or a reply if parent_id is given."
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Not Found - Movie or parent comment."},
        400: {"description": "Bad Request - Invalid parent comment."},
    },
)
async def create_movie_comment(
    movie_id: int,
    payload: CommentCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CommentResponseSchema:
    movie = await get_movie_by_id(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    if payload.parent_id is not None:
        parent = await get_comment_by_id(db, payload.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found.",
            )
        if parent.movie_id != movie_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment belongs to another movie.",
            )

    comment = await create_comment(
        db,
        user.id,
        movie_id,
        payload.content,
        payload.parent_id,
    )
    await db.commit()
    await db.refresh(comment)

    return CommentResponseSchema(
        id=comment.id,
        user_id=comment.user_id,
        movie_id=comment.movie_id,
        parent_id=comment.parent_id,
        content=comment.content,
        created_at=comment.created_at,
        replies=[],
    )


@router.get(
    "/{movie_id}/comments/",
    response_model=list[CommentResponseSchema],
    summary="List Movie Comments",
    description="Return top-level comments for a movie with replies.",
    status_code=status.HTTP_200_OK,
)
async def list_movie_comments(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CommentResponseSchema]:
    comments = await get_movie_comments(db, movie_id)
    return [
        CommentResponseSchema.model_validate(comment)
        for comment in comments
    ]
