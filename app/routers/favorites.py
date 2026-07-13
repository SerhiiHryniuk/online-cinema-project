from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_favorite_repo, get_movie_repo
from app.models.accounts import User
from app.repositories.favorites import FavoriteRepository

from app.repositories.movies import MovieRepository
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
    favorites: Annotated[FavoriteRepository, Depends(get_favorite_repo)],
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

    items, total = await favorites.get_favorite_movies_page(
        user.id, page, per_page, params
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
    favorites: Annotated[FavoriteRepository, Depends(get_favorite_repo)],
    movies: Annotated[MovieRepository, Depends(get_movie_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> FavoriteResponseSchema:
    movie = await movies.get_by_id(movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    existing = await favorites.get(user.id, movie_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in favorites.",
        )

    favorite = await favorites.add(user.id, movie_id)
    await favorites.db.commit()
    await favorites.db.refresh(favorite)

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
    favorites: Annotated[FavoriteRepository, Depends(get_favorite_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    removed = await favorites.remove(user.id, movie_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not in favorites.",
        )

    await favorites.db.commit()
