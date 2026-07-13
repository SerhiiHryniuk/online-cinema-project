from decimal import Decimal

from app.models.movies import Certification, Movie
from app.repositories.genres import GenreRepository


async def test_create_genre(db_session):
    repo = GenreRepository(db_session)
    genre = await repo.create("Sci-Fi")
    await db_session.commit()

    assert genre.id is not None
    assert genre.name == "Sci-Fi"


async def test_get_genre_by_name(db_session):
    repo = GenreRepository(db_session)
    await repo.create("Drama")
    await db_session.commit()

    found = await repo.get_by_name("Drama")

    assert found is not None
    assert found.name == "Drama"


async def test_update_genre(db_session):
    repo = GenreRepository(db_session)
    genre = await repo.create("Sci-Fi")
    await db_session.commit()

    updated = await repo.update(genre, "Science Fiction")
    await db_session.commit()

    assert updated.id == genre.id
    assert updated.name == "Science Fiction"


async def test_delete_genre(db_session):
    repo = GenreRepository(db_session)
    genre = await repo.create("Horror")
    await db_session.commit()
    genre_id = genre.id

    await repo.delete(genre)
    await db_session.commit()

    found = await repo.get_by_id(genre_id)
    assert found is None


async def test_get_genre_by_id_missing(db_session):
    repo = GenreRepository(db_session)

    found = await repo.get_by_id(999)

    assert found is None


async def test_genres_with_counts(db_session):
    repo = GenreRepository(db_session)

    cert = Certification(name="PG-13")
    scifi = await repo.create("Sci-Fi")
    drama = await repo.create("Drama")
    db_session.add(cert)
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

    rows = await repo.get_with_counts()
    counts = {genre.name: count for genre, count in rows}

    assert counts["Sci-Fi"] == 1
    assert counts["Drama"] == 1


async def test_genre_with_no_movies_has_zero_count(db_session):
    repo = GenreRepository(db_session)
    await repo.create("Horror")
    await db_session.commit()

    rows = await repo.get_with_counts()
    counts = {genre.name: count for genre, count in rows}

    assert counts["Horror"] == 0
