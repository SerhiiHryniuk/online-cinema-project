from typing import Any

from sqlalchemy import func, or_, select, Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.movies import Certification, Director, Genre, Movie, Star
from app.models.orders import OrderItem
from app.repositories.base import BaseRepository
from app.schemas.movie_admin import MovieCreateSchema, MovieUpdateSchema
from app.schemas.movies import (
    MovieFilterParams,
    MovieSortField,
    MovieSortOrder,
)


class MovieRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _apply_filters(self, stmt: Select, params: MovieFilterParams) -> Select:
        if params.year is not None:
            stmt = stmt.where(Movie.year == params.year)

        if params.min_imdb is not None:
            stmt = stmt.where(Movie.imdb >= params.min_imdb)

        if params.max_imdb is not None:
            stmt = stmt.where(Movie.imdb <= params.max_imdb)

        if params.search:
            term = f"%{params.search}%"
            stmt = (
                stmt.outerjoin(Movie.stars)
                .outerjoin(Movie.directors)
                .where(
                    or_(
                        Movie.name.ilike(term),
                        Movie.description.ilike(term),
                        Star.name.ilike(term),
                        Director.name.ilike(term),
                    )
                )
                .distinct()
            )

        return stmt

    def _apply_sorting(self, stmt: Select, params: MovieFilterParams) -> Select:
        sort_columns = {
            MovieSortField.PRICE: Movie.price,
            MovieSortField.YEAR: Movie.year,
            MovieSortField.IMDB: Movie.imdb,
            MovieSortField.VOTES: Movie.votes,
        }
        column = sort_columns[params.sort_by]

        if params.sort_order == MovieSortOrder.DESC:
            column = column.desc()  # type: ignore[assignment]

        return stmt.order_by(column, Movie.id)

    def build_filtered_sorted_stmt(
        self, base_stmt: Select, params: MovieFilterParams
    ) -> Select:
        filtered = self._apply_filters(base_stmt, params)
        return self._apply_sorting(filtered, params)

    async def count_filtered(self, base_stmt: Select, params: MovieFilterParams) -> int:
        filtered_stmt = self._apply_filters(base_stmt, params)
        count_stmt = select(func.count()).select_from(
            filtered_stmt.order_by(None).subquery()
        )
        result = await self.db.execute(count_stmt)
        return result.scalar_one()

    async def get_page(
        self,
        page: int,
        per_page: int,
        params: MovieFilterParams,
    ) -> tuple[list[Movie], int]:
        base_stmt = select(Movie)
        total = await self.count_filtered(base_stmt, params)

        sorted_stmt = self.build_filtered_sorted_stmt(base_stmt, params)
        offset = (page - 1) * per_page
        page_stmt = sorted_stmt.offset(offset).limit(per_page)

        items_result = await self.db.execute(page_stmt)
        items = list(items_result.scalars().unique().all())

        return items, total

    async def get_by_id(self, movie_id: int) -> Movie | None:
        stmt = select(Movie).where(Movie.id == movie_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_admin(self, movie_id: int) -> Movie | None:
        stmt = (
            select(Movie)
            .where(Movie.id == movie_id)
            .options(
                selectinload(Movie.genres),
                selectinload(Movie.stars),
                selectinload(Movie.directors),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _validate_ids(
        self,
        model: Any,
        ids: list[int],
        label: str,
    ) -> list:
        if not ids:
            return []

        unique_ids = set(ids)
        res = await self.db.execute(
            select(model).where(model.id.in_(unique_ids))
        )
        found = list(res.scalars().all())

        if len(found) != len(unique_ids):
            found_ids = {obj.id for obj in found}
            missing = sorted(unique_ids - found_ids)
            raise ValueError(
                f"{label} with ids {missing} do not exist."
            )

        return found

    async def _validate_certification(self, certification_id: int) -> None:
        res = await self.db.execute(
            select(Certification).where(
                Certification.id == certification_id
            )
        )
        if res.scalars().first() is None:
            raise ValueError(
                f"Certification with id {certification_id} does not exist."
            )

    async def create(self, payload: MovieCreateSchema) -> Movie:
        await self._validate_certification(payload.certification_id)
        genres = await self._validate_ids(Genre, payload.genre_ids, "Genres")
        stars = await self._validate_ids(Star, payload.star_ids, "Stars")
        directors = await self._validate_ids(
            Director, payload.director_ids, "Directors"
        )

        movie = Movie(
            name=payload.name,
            year=payload.year,
            time=payload.time,
            imdb=payload.imdb,
            votes=payload.votes,
            meta_score=payload.meta_score,
            gross=payload.gross,
            description=payload.description,
            price=payload.price,
            certification_id=payload.certification_id,
            genres=genres,
            stars=stars,
            directors=directors,
        )
        self.db.add(movie)
        await self.db.flush()
        return movie

    async def update(self, movie: Movie, payload: MovieUpdateSchema) -> Movie:
        if payload.certification_id is not None:
            await self._validate_certification(payload.certification_id)

        data = payload.model_dump(
            exclude_unset=True,
            exclude={"genre_ids", "star_ids", "director_ids"},
        )
        for field, value in data.items():
            setattr(movie, field, value)

        if payload.genre_ids is not None:
            movie.genres = await self._validate_ids(
                Genre, payload.genre_ids, "Genres"
            )

        if payload.star_ids is not None:
            movie.stars = await self._validate_ids(
                Star, payload.star_ids, "Stars"
            )

        if payload.director_ids is not None:
            movie.directors = await self._validate_ids(
                Director, payload.director_ids, "Directors"
            )

        await self.db.flush()
        return movie

    async def has_purchases(self, movie_id: int) -> bool:
        stmt = select(func.count()).select_from(OrderItem).where(
            OrderItem.movie_id == movie_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def delete(self, movie: Movie) -> None:
        await self.db.delete(movie)
        await self.db.flush()
