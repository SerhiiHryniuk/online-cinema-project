from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.movies import _apply_filters, _apply_sorting
from app.models.interactions import Favorite
from app.models.movies import Movie
from app.schemas.movies import MovieFilterParams


async def get_favorite(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> Favorite | None:
    stmt = select(Favorite).where(
        Favorite.user_id == user_id,
        Favorite.movie_id == movie_id,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def add_favorite(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> Favorite:
    favorite = Favorite(user_id=user_id, movie_id=movie_id)
    db.add(favorite)
    await db.flush()
    return favorite


async def remove_favorite(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> bool:
    favorite = await get_favorite(db, user_id, movie_id)
    if favorite is None:
        return False

    await db.delete(favorite)
    await db.flush()
    return True


async def get_favorite_movies_page(
    db: AsyncSession,
    user_id: int,
    page: int,
    per_page: int,
    params: MovieFilterParams,
) -> tuple[list[Movie], int]:
    base_stmt = (
        select(Movie)
        .join(Favorite, Favorite.movie_id == Movie.id)
        .where(Favorite.user_id == user_id)
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

    return items, total
