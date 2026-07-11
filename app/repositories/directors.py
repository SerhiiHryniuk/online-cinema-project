from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Director
from app.repositories.base import BaseRepository


class DirectorRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_all(self) -> list[Director]:
        stmt = select(Director).order_by(Director.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, director_id: int) -> Director | None:
        stmt = select(Director).where(Director.id == director_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Director | None:
        stmt = select(Director).where(Director.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, name: str) -> Director:
        director = Director(name=name)
        self.db.add(director)
        await self.db.flush()
        return director

    async def update(self, director: Director, name: str) -> Director:
        director.name = name
        await self.db.flush()
        return director

    async def delete(self, director: Director) -> None:
        await self.db.delete(director)
        await self.db.flush()
