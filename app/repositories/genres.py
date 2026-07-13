from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movies import Genre, movie_genres
from app.repositories.base import BaseRepository


class GenreRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_with_counts(self) -> list[tuple[Genre, int]]:
        stmt = (
            select(Genre, func.count(movie_genres.c.movie_id))
            .outerjoin(
                movie_genres,
                Genre.id == movie_genres.c.genre_id,
            )
            .group_by(Genre.id)
            .order_by(Genre.name)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_by_id(self, genre_id: int) -> Genre | None:
        stmt = select(Genre).where(Genre.id == genre_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Genre | None:
        stmt = select(Genre).where(Genre.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, name: str) -> Genre:
        genre = Genre(name=name)
        self.db.add(genre)
        await self.db.flush()
        return genre

    async def update(self, genre: Genre, name: str) -> Genre:
        genre.name = name
        await self.db.flush()
        return genre

    async def delete(self, genre: Genre) -> None:
        await self.db.delete(genre)
        await self.db.flush()
