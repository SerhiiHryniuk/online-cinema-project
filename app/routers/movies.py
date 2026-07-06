from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.movies import get_movie_by_id, get_movies_page
from app.db.session import get_db
from app.schemas.movies import (
    MovieDetailSchema,
    MovieFilterParams,
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieSortField,
    MovieSortOrder,
)

router = APIRouter()


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="List Movies",
    description=(
        "Return a paginated list of movies with optional "
        "filtering, sorting and search."
    ),
    status_code=status.HTTP_200_OK,
)
async def list_movies(
    db: Annotated[AsyncSession, Depends(get_db)],
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

    items, total = await get_movies_page(db, page, per_page, params)
    total_pages = (total + per_page - 1) // per_page

    return MovieListResponseSchema(
        items=[MovieListItemSchema.model_validate(m) for m in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get Movie Details",
    description="Return detailed information about a single movie by ID.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Not Found - Movie does not exist."},
    },
)
async def get_movie(
    db: Annotated[AsyncSession, Depends(get_db)],
    movie_id: int,
) -> MovieDetailSchema:
    movie = await get_movie_by_id(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found.",
        )

    return MovieDetailSchema.model_validate(movie)
