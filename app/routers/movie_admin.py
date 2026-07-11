from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_movie_repo
from app.crud.carts import check_movie_in_any_cart
from app.db.session import get_db
from app.repositories.movies import MovieRepository
from app.schemas.movie_admin import (
    MovieCreateSchema,
    MovieUpdateSchema,
)
from app.schemas.movies import MovieDetailSchema

router = APIRouter()


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Create a Movie",
    description="Create a new movie. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        422: {"description": "Unprocessable - Invalid related IDs."},
    },
)
async def create_new_movie(
    payload: MovieCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
) -> MovieDetailSchema:
    try:
        movie = await movies.create(payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    await db.commit()
    await db.refresh(movie)

    return MovieDetailSchema.model_validate(movie)


@router.put(
    "/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Update a Movie",
    description="Update a movie. Moderator or admin only.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Movie does not exist."},
        422: {"description": "Unprocessable - Invalid related IDs."},
    },
)
async def update_existing_movie(
    movie_id: int,
    payload: MovieUpdateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
) -> MovieDetailSchema:
    movie = await movies.get_admin(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    try:
        movie = await movies.update(movie, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    await db.commit()
    await db.refresh(movie)

    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/{movie_id}/",
    summary="Delete a Movie",
    description=(
        "Delete a movie. Moderator or admin only. "
        "A movie that has been purchased cannot be deleted."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Movie does not exist."},
        409: {
            "description": (
                "Conflict - Movie has purchases and cannot be deleted."
            )
        },
    },
)
async def delete_existing_movie(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
) -> None:
    movie = await movies.get_admin(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    if await movies.has_purchases(movie_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie has purchases and cannot be deleted.",
        )

    if await check_movie_in_any_cart(db, movie_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete movie, it currently exists in user carts.",
        )

    await movies.delete(movie)
    await db.commit()
