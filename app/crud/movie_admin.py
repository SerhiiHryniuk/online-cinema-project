from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.movies import (
    Certification,
    Director,
    Genre,
    Movie,
    Star,
)
from app.models.orders import OrderItem
from app.schemas.movie_admin import MovieCreateSchema, MovieUpdateSchema


async def _validate_ids(
    db: AsyncSession,
    model,
    ids: list[int],
    label: str,
) -> list:
    if not ids:
        return []

    unique_ids = set(ids)
    res = await db.execute(
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


async def _validate_certification(
    db: AsyncSession,
    certification_id: int,
) -> None:
    res = await db.execute(
        select(Certification).where(
            Certification.id == certification_id
        )
    )
    if res.scalars().first() is None:
        raise ValueError(
            f"Certification with id {certification_id} does not exist."
        )


async def get_movie_admin(
    db: AsyncSession,
    movie_id: int,
) -> Movie | None:
    stmt = (
        select(Movie)
        .where(Movie.id == movie_id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_movie(
    db: AsyncSession,
    payload: MovieCreateSchema,
) -> Movie:
    await _validate_certification(db, payload.certification_id)
    genres = await _validate_ids(
        db, Genre, payload.genre_ids, "Genres"
    )
    stars = await _validate_ids(
        db, Star, payload.star_ids, "Stars"
    )
    directors = await _validate_ids(
        db, Director, payload.director_ids, "Directors"
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
    db.add(movie)
    await db.flush()
    return movie


async def update_movie(
    db: AsyncSession,
    movie: Movie,
    payload: MovieUpdateSchema,
) -> Movie:
    if payload.certification_id is not None:
        await _validate_certification(db, payload.certification_id)

    data = payload.model_dump(
        exclude_unset=True,
        exclude={"genre_ids", "star_ids", "director_ids"},
    )
    for field, value in data.items():
        setattr(movie, field, value)

    if payload.genre_ids is not None:
        movie.genres = await _validate_ids(
            db, Genre, payload.genre_ids, "Genres"
        )

    if payload.star_ids is not None:
        movie.stars = await _validate_ids(
            db, Star, payload.star_ids, "Stars"
        )

    if payload.director_ids is not None:
        movie.directors = await _validate_ids(
            db, Director, payload.director_ids, "Directors"
        )

    await db.flush()
    return movie


async def movie_has_purchases(
    db: AsyncSession,
    movie_id: int,
) -> bool:
    stmt = select(func.count()).select_from(OrderItem).where(
        OrderItem.movie_id == movie_id
    )
    result = await db.execute(stmt)
    return result.scalar_one() > 0


async def delete_movie(
    db: AsyncSession,
    movie: Movie,
) -> None:
    await db.delete(movie)
    await db.flush()
