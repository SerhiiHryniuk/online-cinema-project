from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_movie_repo, get_rating_repo
from app.db.session import get_db
from app.models.accounts import User
from app.repositories.movies import MovieRepository
from app.repositories.ratings import RatingRepository
from app.schemas.ratings import (
    MovieRatingSummarySchema,
    RatingRequestSchema,
    RatingResponseSchema,
)

router = APIRouter()


@router.put(
    "/{movie_id}/rating/",
    response_model=RatingResponseSchema,
    summary="Rate a Movie",
    description="Set or update the current user's rating for a movie.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Not Found - Movie does not exist."},
    },
)
async def set_movie_rating(
    movie_id: int,
    payload: RatingRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    ratings: Annotated[RatingRepository, Depends(get_rating_repo)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> RatingResponseSchema:
    movie = await movies.get_by_id(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    rating = await ratings.set_rating(user.id, movie_id, payload.score)
    await db.commit()
    await db.refresh(rating)

    return RatingResponseSchema.model_validate(rating)


@router.delete(
    "/{movie_id}/rating/",
    summary="Remove a Movie Rating",
    description="Remove the current user's rating from a movie.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Not Found - No rating to remove."},
    },
)
async def delete_movie_rating(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    ratings: Annotated[RatingRepository, Depends(get_rating_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await ratings.remove_rating(user.id, movie_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rating to remove.",
        )

    await db.commit()


@router.get(
    "/{movie_id}/rating/",
    response_model=MovieRatingSummarySchema,
    summary="Get Movie Rating Summary",
    description="Return the average score and number of ratings.",
    status_code=status.HTTP_200_OK,
)
async def get_movie_rating(
    movie_id: int,
    ratings: Annotated[RatingRepository, Depends(get_rating_repo)],
) -> MovieRatingSummarySchema:
    average, count = await ratings.get_movie_rating_summary(movie_id)
    return MovieRatingSummarySchema(average=average, count=count)
