from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.movies import Director, Genre, Movie, Star
from app.models.orders import OrderItem
from app.schemas.movie_admin import MovieCreateSchema, MovieUpdateSchema


async def _load_related(
    db: AsyncSession,
    genre_ids: list[int],
    star_ids: list[int],
    director_ids: list[int],
) -> tuple[list[Genre], list[Star], list[Director]]:
    genres = []
    if genre_ids:
        res = await db.execute(
            select(Genre).where(Genre.id.in_(genre_ids))
        )
        genres = list(res.scalars().all())

    stars = []
    if star_ids:
        res = await db.execute(
            select(Star).where(Star.id.in_(star_ids))
        )
        stars = list(res.scalars().all())

    directors = []
    if director_ids:
        res = await db.execute(
            select(Director).where(Director.id.in_(director_ids))
        )
        directors = list(res.scalars().all())

    return genres, stars, directors


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
    genres, stars, directors = await _load_related(
        db,
        payload.genre_ids,
        payload.star_ids,
        payload.director_ids,
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
    data = payload.model_dump(
        exclude_unset=True,
        exclude={"genre_ids", "star_ids", "director_ids"},
    )
    for field, value in data.items():
        setattr(movie, field, value)

    if payload.genre_ids is not None:
        res = await db.execute(
            select(Genre).where(Genre.id.in_(payload.genre_ids))
        )
        movie.genres = list(res.scalars().all())

    if payload.star_ids is not None:
        res = await db.execute(
            select(Star).where(Star.id.in_(payload.star_ids))
        )
        movie.stars = list(res.scalars().all())

    if payload.director_ids is not None:
        res = await db.execute(
            select(Director).where(
                Director.id.in_(payload.director_ids)
            )
        )
        movie.directors = list(res.scalars().all())

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
