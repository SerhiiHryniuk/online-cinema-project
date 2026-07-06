from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Certification


async def get_all_certifications(
    db: AsyncSession,
) -> list[Certification]:
    stmt = select(Certification).order_by(Certification.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_certification_by_id(
    db: AsyncSession,
    certification_id: int,
) -> Certification | None:
    stmt = select(Certification).where(
        Certification.id == certification_id
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_certification_by_name(
    db: AsyncSession,
    name: str,
) -> Certification | None:
    stmt = select(Certification).where(
        Certification.name == name
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_certification(
    db: AsyncSession,
    name: str,
) -> Certification:
    certification = Certification(name=name)
    db.add(certification)
    await db.flush()
    return certification


async def update_certification(
    db: AsyncSession,
    certification: Certification,
    name: str,
) -> Certification:
    certification.name = name
    await db.flush()
    return certification


async def delete_certification(
    db: AsyncSession,
    certification: Certification,
) -> None:
    await db.delete(certification)
    await db.flush()
