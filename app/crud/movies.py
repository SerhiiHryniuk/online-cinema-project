from sqlalchemy import func, or_, select, Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Director, Movie, Star
from app.schemas.movies import (
    MovieFilterParams,
    MovieSortField,
    MovieSortOrder,
)


def _apply_filters(stmt: Select, params: MovieFilterParams) -> Select:
    if params.year is not None:
        stmt = stmt.where(Movie.year == params.year)

    if params.min_imdb is not None:
        stmt = stmt.where(Movie.imdb >= params.min_imdb)

    if params.max_imdb is not None:
        stmt = stmt.where(Movie.imdb <= params.max_imdb)

    if params.search:
        term = f"%{params.search}%"
        stmt = (
            stmt.outerjoin(Movie.stars)
            .outerjoin(Movie.directors)
            .where(
                or_(
                    Movie.name.ilike(term),
                    Movie.description.ilike(term),
                    Star.name.ilike(term),
                    Director.name.ilike(term),
                )
            )
            .distinct()
        )

    return stmt


def _apply_sorting(stmt: Select, params: MovieFilterParams) -> Select:
    sort_columns = {
        MovieSortField.PRICE: Movie.price,
        MovieSortField.YEAR: Movie.year,
        MovieSortField.IMDB: Movie.imdb,
        MovieSortField.VOTES: Movie.votes,
    }
    column = sort_columns[params.sort_by]

    if params.sort_order == MovieSortOrder.DESC:
        column = column.desc()  # type: ignore[assignment]

    return stmt.order_by(column, Movie.id)


async def get_movies_page(
    db: AsyncSession,
    page: int,
    per_page: int,
    params: MovieFilterParams,
) -> tuple[list[Movie], int]:
    base_stmt = select(Movie)
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

    return items, total


async def get_movie_by_id(db: AsyncSession, movie_id: int) -> Movie | None:
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    return result.scalars().first()
