from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import allowed_roles_user
from app.crud.movie_admin import (
    create_movie,
    delete_movie,
    get_movie_admin,
    movie_has_purchases,
    update_movie,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
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
    },
)
async def create_new_movie(
    payload: MovieCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> MovieDetailSchema:
    movie = await create_movie(db, payload)
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
    },
)
async def update_existing_movie(
    movie_id: int,
    payload: MovieUpdateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> MovieDetailSchema:
    movie = await get_movie_admin(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    movie = await update_movie(db, movie, payload)
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
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> None:
    movie = await get_movie_admin(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    if await movie_has_purchases(db, movie_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie has purchases and cannot be deleted.",
        )

    await delete_movie(db, movie)
    await db.commit()
