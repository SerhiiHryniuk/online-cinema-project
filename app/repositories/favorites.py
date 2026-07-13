from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactions import Favorite
from app.models.movies import Movie
from app.repositories.base import BaseRepository
from app.repositories.movies import MovieRepository
from app.schemas.movies import MovieFilterParams


class FavoriteRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._movies = MovieRepository(db)

    async def get(self, user_id: int, movie_id: int) -> Favorite | None:
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.movie_id == movie_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def add(self, user_id: int, movie_id: int) -> Favorite:
        favorite = Favorite(user_id=user_id, movie_id=movie_id)
        self.db.add(favorite)
        await self.db.flush()
        return favorite

    async def remove(self, user_id: int, movie_id: int) -> bool:
        favorite = await self.get(user_id, movie_id)
        if favorite is None:
            return False

        await self.db.delete(favorite)
        await self.db.flush()
        return True

    async def get_favorite_movies_page(
        self,
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

        total = await self._movies.count_filtered(base_stmt, params)
        sorted_stmt = self._movies.build_filtered_sorted_stmt(base_stmt, params)

        offset = (page - 1) * per_page
        page_stmt = sorted_stmt.offset(offset).limit(per_page)

        items_result = await self.db.execute(page_stmt)
        items = list(items_result.scalars().unique().all())

        return items, total
