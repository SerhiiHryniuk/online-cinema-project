from decimal import Decimal

from app.crud.genres import get_genre_by_id, get_genres_with_counts
from app.models.movies import Certification, Genre, Movie


async def _setup(db_session):
    cert = Certification(name="PG-13")
    scifi = Genre(name="Sci-Fi")
    drama = Genre(name="Drama")
    db_session.add_all([cert, scifi, drama])
    await db_session.commit()

    inception = Movie(
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=2000000,
        description="A thief who steals corporate secrets.",
        price=Decimal("9.99"),
        certification_id=cert.id,
    )
    inception.genres.append(scifi)

    godfather = Movie(
        name="The Godfather",
        year=1972,
        time=175,
        imdb=9.2,
        votes=1900000,
        description="The aging patriarch of a crime dynasty.",
        price=Decimal("6.99"),
        certification_id=cert.id,
    )
    godfather.genres.append(drama)

    db_session.add_all([inception, godfather])
    await db_session.commit()

    return scifi, drama


async def test_genres_with_counts(db_session):
    scifi, drama = await _setup(db_session)

    rows = await get_genres_with_counts(db_session)
    counts = {genre.name: count for genre, count in rows}

    assert counts["Sci-Fi"] == 1
    assert counts["Drama"] == 1


async def test_genre_with_no_movies_has_zero_count(db_session):
    empty = Genre(name="Horror")
    db_session.add(empty)
    await db_session.commit()

    rows = await get_genres_with_counts(db_session)
    counts = {genre.name: count for genre, count in rows}

    assert counts["Horror"] == 0


async def test_get_genre_by_id(db_session):
    scifi, _ = await _setup(db_session)

    found = await get_genre_by_id(db_session, scifi.id)

    assert found is not None
    assert found.name == "Sci-Fi"


async def test_get_genre_by_id_missing(db_session):
    found = await get_genre_by_id(db_session, 999)

    assert found is None
