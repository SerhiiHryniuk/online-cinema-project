import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Certification,
    Comment,
    Favorite,
    Like,
    LikeType,
    Movie,
    Notification,
    NotificationType,
    Rating,
    User,
    UserGroup,
    UserGroupEnum,
)


async def _make_user_and_movie(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="viewer@example.com",
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
        price=9.99,
        certification_id=cert.id,
    )
    db_session.add(movie)
    await db_session.commit()

    return user, movie


async def test_create_like(db_session):
    user, movie = await _make_user_and_movie(db_session)

    like = Like(user_id=user.id, movie_id=movie.id, type=LikeType.LIKE)
    db_session.add(like)
    await db_session.commit()

    assert like.id is not None
    assert like.type == LikeType.LIKE


async def test_like_unique_per_user_and_movie(db_session):
    user, movie = await _make_user_and_movie(db_session)

    first = Like(user_id=user.id, movie_id=movie.id, type=LikeType.LIKE)
    db_session.add(first)
    await db_session.commit()

    duplicate = Like(
        user_id=user.id, movie_id=movie.id, type=LikeType.DISLIKE
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_create_rating(db_session):
    user, movie = await _make_user_and_movie(db_session)

    rating = Rating(user_id=user.id, movie_id=movie.id, score=9)
    db_session.add(rating)
    await db_session.commit()

    assert rating.id is not None
    assert rating.score == 9


async def test_favorite_unique(db_session):
    user, movie = await _make_user_and_movie(db_session)

    fav = Favorite(user_id=user.id, movie_id=movie.id)
    db_session.add(fav)
    await db_session.commit()

    duplicate = Favorite(user_id=user.id, movie_id=movie.id)
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_comment_with_reply(db_session):
    user, movie = await _make_user_and_movie(db_session)

    parent = Comment(
        user_id=user.id, movie_id=movie.id, content="Great movie!"
    )
    db_session.add(parent)
    await db_session.commit()

    reply = Comment(
        user_id=user.id,
        movie_id=movie.id,
        content="I agree!",
        parent_id=parent.id,
    )
    db_session.add(reply)
    await db_session.commit()

    result = await db_session.execute(
        select(Comment).where(Comment.id == reply.id)
    )
    loaded_reply = result.scalar_one()

    assert loaded_reply.parent_id == parent.id


async def test_create_notification(db_session):
    user, movie = await _make_user_and_movie(db_session)

    notification = Notification(
        user_id=user.id,
        type=NotificationType.COMMENT_REPLY,
        message="Someone replied to your comment",
    )
    db_session.add(notification)
    await db_session.commit()

    assert notification.id is not None
    assert notification.is_read is False
