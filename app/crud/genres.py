from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Genre, movie_genres


async def get_genres_with_counts(
    db: AsyncSession,
) -> list[tuple[Genre, int]]:
    stmt = (
        select(Genre, func.count(movie_genres.c.movie_id))
        .outerjoin(
            movie_genres,
            Genre.id == movie_genres.c.genre_id,
        )
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_genre_by_id(
    db: AsyncSession,
    genre_id: int,
) -> Genre | None:
    stmt = select(Genre).where(Genre.id == genre_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_genre_by_name(
    db: AsyncSession,
    name: str,
) -> Genre | None:
    stmt = select(Genre).where(Genre.name == name)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_genre(
    db: AsyncSession,
    name: str,
) -> Genre:
    genre = Genre(name=name)
    db.add(genre)
    await db.flush()
    return genre


async def update_genre(
    db: AsyncSession,
    genre: Genre,
    name: str,
) -> Genre:
    genre.name = name
    await db.flush()
    return genre


async def delete_genre(
    db: AsyncSession,
    genre: Genre,
) -> None:
    await db.delete(genre)
    await db.flush()
