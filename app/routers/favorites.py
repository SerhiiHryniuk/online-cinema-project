from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud.favorites import (
    add_favorite,
    get_favorite,
    get_favorite_movies_page,
    remove_favorite,
)
from app.crud.movies import get_movie_by_id
from app.db.session import get_db
from app.models.accounts import User
from app.schemas.favorites import FavoriteResponseSchema
from app.schemas.movies import (
    MovieFilterParams,
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieSortField,
    MovieSortOrder,
)

router = APIRouter()


@router.get(
    "/favorites/",
    response_model=MovieListResponseSchema,
    summary="List Favorite Movies",
    description=(
        "Return the current user's favorite movies with optional "
        "filtering, sorting and search."
    ),
    status_code=status.HTTP_200_OK,
)
async def list_favorites(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
    year: Annotated[Optional[int], Query()] = None,
    min_imdb: Annotated[Optional[float], Query(ge=0, le=10)] = None,
    max_imdb: Annotated[Optional[float], Query(ge=0, le=10)] = None,
    search: Annotated[Optional[str], Query()] = None,
    sort_by: Annotated[MovieSortField, Query()] = MovieSortField.YEAR,
    sort_order: Annotated[MovieSortOrder, Query()] = MovieSortOrder.DESC,
) -> MovieListResponseSchema:
    params = MovieFilterParams(
        year=year,
        min_imdb=min_imdb,
        max_imdb=max_imdb,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    items, total = await get_favorite_movies_page(
        db, user.id, page, per_page, params
    )
    total_pages = (total + per_page - 1) // per_page

    return MovieListResponseSchema(
        items=[MovieListItemSchema.model_validate(m) for m in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.post(
    "/{movie_id}/favorite/",
    response_model=FavoriteResponseSchema,
    summary="Add Movie to Favorites",
    description="Add a movie to the current user's favorites.",
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Not Found - Movie does not exist."},
        409: {"description": "Conflict - Movie already in favorites."},
    },
)
async def add_movie_favorite(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> FavoriteResponseSchema:
    movie = await get_movie_by_id(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    existing = await get_favorite(db, user.id, movie_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in favorites.",
        )

    favorite = await add_favorite(db, user.id, movie_id)
    await db.commit()
    await db.refresh(favorite)

    return FavoriteResponseSchema.model_validate(favorite)


@router.delete(
    "/{movie_id}/favorite/",
    summary="Remove Movie from Favorites",
    description="Remove a movie from the current user's favorites.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Not Found - Movie not in favorites."},
    },
)
async def remove_movie_favorite(
    movie_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await remove_favorite(db, user.id, movie_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not in favorites.",
        )

    await db.commit()
