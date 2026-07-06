from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.movies import get_movie_by_id
from app.crud.ratings import (
    get_movie_rating_summary,
    remove_rating,
    set_rating,
)
from app.db.session import get_db
from app.models.accounts import User
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
    user: Annotated[User, Depends(get_current_user)],
) -> RatingResponseSchema:
    movie = await get_movie_by_id(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    rating = await set_rating(db, user.id, movie_id, payload.score)
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
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await remove_rating(db, user.id, movie_id)
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MovieRatingSummarySchema:
    average, count = await get_movie_rating_summary(db, movie_id)
    return MovieRatingSummarySchema(average=average, count=count)
