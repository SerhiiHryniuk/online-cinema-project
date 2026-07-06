from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Director


async def get_all_directors(db: AsyncSession) -> list[Director]:
    stmt = select(Director).order_by(Director.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_director_by_id(
    db: AsyncSession,
    director_id: int,
) -> Director | None:
    stmt = select(Director).where(Director.id == director_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_director_by_name(
    db: AsyncSession,
    name: str,
) -> Director | None:
    stmt = select(Director).where(Director.name == name)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_director(
    db: AsyncSession,
    name: str,
) -> Director:
    director = Director(name=name)
    db.add(director)
    await db.flush()
    return director


async def update_director(
    db: AsyncSession,
    director: Director,
    name: str,
) -> Director:
    director.name = name
    await db.flush()
    return director


async def delete_director(
    db: AsyncSession,
    director: Director,
) -> None:
    await db.delete(director)
    await db.flush()
