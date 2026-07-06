from decimal import Decimal

from app.crud.ratings import (
    get_movie_rating_summary,
    get_user_rating,
    remove_rating,
    set_rating,
)
from app.models.movies import Certification, Movie
from app.models.accounts import User, UserGroup, UserGroupEnum


async def _make_user_and_movie(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="rater@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    cert = Certification(name="PG-13")
    db_session.add_all([user, cert])
    await db_session.commit()

    movie = Movie(
        name="Inception",
        year=2010,
        time=148,
        imdb=8.8,
        votes=2000000,
        description="A thief who steals corporate secrets.",
        price=Decimal("9.99"),
        certification_id=cert.id,
    )
    db_session.add(movie)
    await db_session.commit()

    return user, movie


async def test_set_rating_creates(db_session):
    user, movie = await _make_user_and_movie(db_session)

    rating = await set_rating(db_session, user.id, movie.id, 9)
    await db_session.commit()

    assert rating.id is not None
    assert rating.score == 9


async def test_set_rating_updates_existing(db_session):
    user, movie = await _make_user_and_movie(db_session)

    first = await set_rating(db_session, user.id, movie.id, 7)
    await db_session.commit()
    first_id = first.id

    updated = await set_rating(db_session, user.id, movie.id, 10)
    await db_session.commit()

    assert updated.id == first_id
    assert updated.score == 10


async def test_remove_rating(db_session):
    user, movie = await _make_user_and_movie(db_session)

    await set_rating(db_session, user.id, movie.id, 8)
    await db_session.commit()

    removed = await remove_rating(db_session, user.id, movie.id)
    await db_session.commit()

    assert removed is True

    rating = await get_user_rating(db_session, user.id, movie.id)
    assert rating is None


async def test_remove_rating_when_none(db_session):
    user, movie = await _make_user_and_movie(db_session)

    removed = await remove_rating(db_session, user.id, movie.id)
    assert removed is False


async def test_rating_summary_empty(db_session):
    user, movie = await _make_user_and_movie(db_session)

    average, count = await get_movie_rating_summary(db_session, movie.id)

    assert average == 0.0
    assert count == 0


async def test_rating_summary_average(db_session):
    user, movie = await _make_user_and_movie(db_session)

    other = User(
        email="rater2@example.com",
        hashed_password="hashed",
        group_id=user.group_id,
    )
    db_session.add(other)
    await db_session.commit()

    await set_rating(db_session, user.id, movie.id, 8)
    await set_rating(db_session, other.id, movie.id, 10)
    await db_session.commit()

    average, count = await get_movie_rating_summary(db_session, movie.id)

    assert average == 9.0
    assert count == 2
