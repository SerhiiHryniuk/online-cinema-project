from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Certification
from app.repositories.base import BaseRepository


class CertificationRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_all(self) -> list[Certification]:
        stmt = select(Certification).order_by(Certification.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, certification_id: int) -> Certification | None:
        stmt = select(Certification).where(
            Certification.id == certification_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Certification | None:
        stmt = select(Certification).where(Certification.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, name: str) -> Certification:
        certification = Certification(name=name)
        self.db.add(certification)
        await self.db.flush()
        return certification

    async def update(self, certification: Certification, name: str) -> Certification:
        certification.name = name
        await self.db.flush()
        return certification

    async def delete(self, certification: Certification) -> None:
        await self.db.delete(certification)
        await self.db.flush()
