from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.likes import count_movie_likes, remove_like, set_like
from app.crud.movies import get_movie_by_id
from app.db.session import get_db
from app.models.accounts import User
from app.schemas.likes import (
    LikeRequestSchema,
    LikeResponseSchema,
    MovieLikesCountSchema,
)

router = APIRouter()


@router.put(
    "/{movie_id}/like/",
    response_model=LikeResponseSchema,
    summary="Like or Dislike a Movie",
    description="Set or update the current user's reaction to a movie.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Not Found - Movie does not exist."},
    },
)
async def set_movie_like(
    movie_id: int,
    payload: LikeRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> LikeResponseSchema:
    movie = await get_movie_by_id(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    like = await set_like(db, user.id, movie_id, payload.type)
    await db.commit()
    await db.refresh(like)

    return LikeResponseSchema.model_validate(like)


@router.delete(
    "/{movie_id}/like/",
    summary="Remove a Movie Reaction",
    description="Remove the current user's reaction from a movie.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Not Found - No reaction to remove."},
    },
)
async def delete_movie_like(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await remove_like(db, user.id, movie_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reaction to remove.",
        )

    await db.commit()


@router.get(
    "/{movie_id}/likes/",
    response_model=MovieLikesCountSchema,
    summary="Get Movie Likes Count",
    description="Return the number of likes and dislikes for a movie.",
    status_code=status.HTTP_200_OK,
)
async def get_movie_likes(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MovieLikesCountSchema:
    likes, dislikes = await count_movie_likes(db, movie_id)
    return MovieLikesCountSchema(likes=likes, dislikes=dislikes)
