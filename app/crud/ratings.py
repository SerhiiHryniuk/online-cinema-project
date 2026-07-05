from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactions import Rating


async def get_user_rating(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> Rating | None:
    stmt = select(Rating).where(
        Rating.user_id == user_id,
        Rating.movie_id == movie_id,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def set_rating(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
    score: int,
) -> Rating:
    rating = await get_user_rating(db, user_id, movie_id)

    if rating is None:
        rating = Rating(
            user_id=user_id,
            movie_id=movie_id,
            score=score,
        )
        db.add(rating)
    else:
        rating.score = score

    await db.flush()
    return rating


async def remove_rating(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> bool:
    rating = await get_user_rating(db, user_id, movie_id)
    if rating is None:
        return False

    await db.delete(rating)
    await db.flush()
    return True


async def get_movie_rating_summary(
    db: AsyncSession,
    movie_id: int,
) -> tuple[float, int]:
    stmt = select(
        func.avg(Rating.score),
        func.count(Rating.id),
    ).where(Rating.movie_id == movie_id)
    result = await db.execute(stmt)
    average, count = result.one()

    if count == 0:
        return 0.0, 0

    return round(float(average), 2), count
