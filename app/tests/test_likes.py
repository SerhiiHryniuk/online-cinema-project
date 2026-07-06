from decimal import Decimal

from app.crud.likes import (
    count_movie_likes,
    get_user_like,
    remove_like,
    set_like,
)
from app.models.interactions import LikeType
from app.models.movies import Certification, Movie
from app.models.accounts import User, UserGroup, UserGroupEnum


async def _make_user_and_movie(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="liker@example.com",
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


async def test_set_like_creates_reaction(db_session):
    user, movie = await _make_user_and_movie(db_session)

    like = await set_like(db_session, user.id, movie.id, LikeType.LIKE)
    await db_session.commit()

    assert like.id is not None
    assert like.type == LikeType.LIKE


async def test_set_like_updates_existing(db_session):
    user, movie = await _make_user_and_movie(db_session)

    first = await set_like(db_session, user.id, movie.id, LikeType.LIKE)
    await db_session.commit()
    first_id = first.id

    updated = await set_like(
        db_session, user.id, movie.id, LikeType.DISLIKE
    )
    await db_session.commit()

    assert updated.id == first_id
    assert updated.type == LikeType.DISLIKE


async def test_remove_like(db_session):
    user, movie = await _make_user_and_movie(db_session)

    await set_like(db_session, user.id, movie.id, LikeType.LIKE)
    await db_session.commit()

    removed = await remove_like(db_session, user.id, movie.id)
    await db_session.commit()

    assert removed is True

    like = await get_user_like(db_session, user.id, movie.id)
    assert like is None


async def test_remove_like_when_none(db_session):
    user, movie = await _make_user_and_movie(db_session)

    removed = await remove_like(db_session, user.id, movie.id)
    assert removed is False


async def test_count_movie_likes(db_session):
    user, movie = await _make_user_and_movie(db_session)

    await set_like(db_session, user.id, movie.id, LikeType.DISLIKE)
    await db_session.commit()

    likes, dislikes = await count_movie_likes(db_session, movie.id)

    assert likes == 0
    assert dislikes == 1
