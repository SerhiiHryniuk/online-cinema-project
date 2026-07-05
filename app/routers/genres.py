from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import allowed_roles_user
from app.crud.genres import (
    create_genre,
    delete_genre,
    get_genre_by_id,
    get_genre_by_name,
    get_genres_with_counts,
    update_genre,
)
from app.crud.movies import _apply_filters, _apply_sorting
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
from app.models.movies import Movie, movie_genres
from app.schemas.genres import (
    GenreCreateSchema,
    GenreSchema,
    GenreWithCountSchema,
)
from app.schemas.movies import (
    MovieFilterParams,
    MovieListItemSchema,
    MovieListResponseSchema,
    MovieSortField,
    MovieSortOrder,
)

router = APIRouter()


@router.get(
    "/",
    response_model=list[GenreWithCountSchema],
    summary="List Genres with Movie Counts",
    description="Return all genres with the number of movies in each.",
    status_code=status.HTTP_200_OK,
)
async def list_genres(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[GenreWithCountSchema]:
    rows = await get_genres_with_counts(db)
    return [
        GenreWithCountSchema(
            id=genre.id,
            name=genre.name,
            movie_count=count,
        )
        for genre, count in rows
    ]


@router.post(
    "/",
    response_model=GenreSchema,
    summary="Create a Genre",
    description="Create a new genre. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        409: {"description": "Conflict - Genre already exists."},
    },
)
async def create_new_genre(
    payload: GenreCreateSchema,
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
) -> GenreSchema:
    existing = await get_genre_by_name(db, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genre already exists.",
        )

    genre = await create_genre(db, payload.name)
    await db.commit()
    await db.refresh(genre)

    return GenreSchema.model_validate(genre)


@router.put(
    "/{genre_id}/",
    response_model=GenreSchema,
    summary="Update a Genre",
    description="Rename a genre. Moderator or admin only.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Genre does not exist."},
        409: {"description": "Conflict - Genre name already taken."},
    },
)
async def update_existing_genre(
    genre_id: int,
    payload: GenreCreateSchema,
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
) -> GenreSchema:
    genre = await get_genre_by_id(db, genre_id)
    if genre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre not found.",
        )

    duplicate = await get_genre_by_name(db, payload.name)
    if duplicate is not None and duplicate.id != genre_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genre name already taken.",
        )

    genre = await update_genre(db, genre, payload.name)
    await db.commit()
    await db.refresh(genre)

    return GenreSchema.model_validate(genre)


@router.delete(
    "/{genre_id}/",
    summary="Delete a Genre",
    description="Delete a genre. Moderator or admin only.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Genre does not exist."},
    },
)
async def delete_existing_genre(
    genre_id: int,
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
    genre = await get_genre_by_id(db, genre_id)
    if genre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre not found.",
        )

    await delete_genre(db, genre)
    await db.commit()


@router.get(
    "/{genre_id}/movies/",
    response_model=MovieListResponseSchema,
    summary="List Movies in a Genre",
    description=(
        "Return a paginated list of movies in a genre with optional "
        "filtering, sorting and search."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Not Found - Genre does not exist."},
    },
)
async def list_genre_movies(
    genre_id: int,
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
    genre = await get_genre_by_id(db, genre_id)
    if genre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre not found.",
        )

    params = MovieFilterParams(
        year=year,
        min_imdb=min_imdb,
        max_imdb=max_imdb,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    base_stmt = (
        select(Movie)
        .join(movie_genres, Movie.id == movie_genres.c.movie_id)
        .where(movie_genres.c.genre_id == genre_id)
    )
    filtered_stmt = _apply_filters(base_stmt, params)

    count_stmt = select(func.count()).select_from(
        filtered_stmt.order_by(None).subquery()
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    sorted_stmt = _apply_sorting(filtered_stmt, params)
    offset = (page - 1) * per_page
    page_stmt = sorted_stmt.offset(offset).limit(per_page)

    items_result = await db.execute(page_stmt)
    items = list(items_result.scalars().unique().all())
    total_pages = (total + per_page - 1) // per_page

    return MovieListResponseSchema(
        items=[MovieListItemSchema.model_validate(m) for m in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )
