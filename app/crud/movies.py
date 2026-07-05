from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Movie


async def get_movies_page(
    db: AsyncSession,
    page: int,
    per_page: int,
) -> tuple[list[Movie], int]:
    total_stmt = select(func.count()).select_from(Movie)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    items_stmt = (
        select(Movie)
        .order_by(Movie.id)
        .offset(offset)
        .limit(per_page)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars().all())

    return items, total


async def get_movie_by_id(db: AsyncSession, movie_id: int) -> Movie | None:
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    return result.scalars().first()
