from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Star
from app.repositories.base import BaseRepository


class StarRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_all(self) -> list[Star]:
        stmt = select(Star).order_by(Star.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, star_id: int) -> Star | None:
        stmt = select(Star).where(Star.id == star_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Star | None:
        stmt = select(Star).where(Star.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, name: str) -> Star:
        star = Star(name=name)
        self.db.add(star)
        await self.db.flush()
        return star

    async def update(self, star: Star, name: str) -> Star:
        star.name = name
        await self.db.flush()
        return star

    async def delete(self, star: Star) -> None:
        await self.db.delete(star)
        await self.db.flush()