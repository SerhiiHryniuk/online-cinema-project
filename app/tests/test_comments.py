from decimal import Decimal

from app.crud.comments import (
    create_comment,
    get_movie_comments,
)
from app.crud.notifications import get_user_notifications
from app.models.movies import Certification, Movie
from app.models.accounts import User, UserGroup, UserGroupEnum


async def _setup(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    author = User(
        email="author@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    replier = User(
        email="replier@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    cert = Certification(name="PG-13")
    db_session.add_all([author, replier, cert])
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

    return author, replier, movie


async def test_create_top_level_comment(db_session):
    author, _, movie = await _setup(db_session)

    comment = await create_comment(
        db_session, author.id, movie.id, "Nice movie!", None
    )
    await db_session.commit()

    assert comment.id is not None
    assert comment.parent_id is None


async def test_create_reply(db_session):
    author, replier, movie = await _setup(db_session)

    parent = await create_comment(
        db_session, author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    reply = await create_comment(
        db_session, replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    assert reply.parent_id == parent.id


async def test_reply_creates_notification(db_session):
    author, replier, movie = await _setup(db_session)

    parent = await create_comment(
        db_session, author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await create_comment(
        db_session, replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    notifications = await get_user_notifications(
        db_session, author.id, False
    )

    assert len(notifications) == 1
    assert notifications[0].user_id == author.id


async def test_reply_to_self_no_notification(db_session):
    author, _, movie = await _setup(db_session)

    parent = await create_comment(
        db_session, author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await create_comment(
        db_session, author.id, movie.id, "Self reply", parent.id
    )
    await db_session.commit()

    notifications = await get_user_notifications(
        db_session, author.id, False
    )

    assert len(notifications) == 0


async def test_get_movie_comments_with_replies(db_session):
    author, replier, movie = await _setup(db_session)

    parent = await create_comment(
        db_session, author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await create_comment(
        db_session, replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    comments = await get_movie_comments(db_session, movie.id)

    assert len(comments) == 1
    assert comments[0].id == parent.id
    assert len(comments[0].replies) == 1
