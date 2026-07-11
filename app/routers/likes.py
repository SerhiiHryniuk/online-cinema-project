from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_like_repo, get_movie_repo
from app.db.session import get_db
from app.models.accounts import User
from app.repositories.likes import LikeRepository
from app.repositories.movies import MovieRepository
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
    likes: Annotated[LikeRepository, Depends(get_like_repo)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> LikeResponseSchema:
    movie = await movies.get_by_id(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    like = await likes.set_like(user.id, movie_id, payload.type)
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
    likes: Annotated[LikeRepository, Depends(get_like_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await likes.remove_like(user.id, movie_id)
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
    likes: Annotated[LikeRepository, Depends(get_like_repo)],
) -> MovieLikesCountSchema:
    like_count, dislike_count = await likes.count_movie_likes(movie_id)
    return MovieLikesCountSchema(likes=like_count, dislikes=dislike_count)
