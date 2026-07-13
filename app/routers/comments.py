from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_comment_repo, get_comment_service, get_current_user, get_movie_repo
from app.db.session import get_db
from app.models.accounts import User
from app.repositories.comments import CommentRepository
from app.repositories.movies import MovieRepository
from app.schemas.comments import (
    CommentCreateSchema,
    CommentResponseSchema,
)
from app.services.comments import CommentService

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
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
    comments: Annotated[CommentRepository, Depends(get_comment_repo)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> CommentResponseSchema:
    movie = await movies.get_by_id(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    if payload.parent_id is not None:
        parent = await comments.get_by_id(payload.parent_id)
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

    comment = await comment_service.create_comment(
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
    comments: Annotated[CommentRepository, Depends(get_comment_repo)],
) -> list[CommentResponseSchema]:
    movie_comments = await comments.get_movie_comments(movie_id)
    return [
        CommentResponseSchema.model_validate(comment)
        for comment in movie_comments
    ]
