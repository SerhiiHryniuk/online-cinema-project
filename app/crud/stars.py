from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Star


async def get_all_stars(db: AsyncSession) -> list[Star]:
    stmt = select(Star).order_by(Star.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_star_by_id(
    db: AsyncSession,
    star_id: int,
) -> Star | None:
    stmt = select(Star).where(Star.id == star_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_star_by_name(
    db: AsyncSession,
    name: str,
) -> Star | None:
    stmt = select(Star).where(Star.name == name)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_star(
    db: AsyncSession,
    name: str,
) -> Star:
    star = Star(name=name)
    db.add(star)
    await db.flush()
    return star


async def update_star(
    db: AsyncSession,
    star: Star,
    name: str,
) -> Star:
    star.name = name
    await db.flush()
    return star


async def delete_star(
    db: AsyncSession,
    star: Star,
) -> None:
    await db.delete(star)
    await db.flush()
