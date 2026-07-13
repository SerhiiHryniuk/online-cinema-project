from decimal import Decimal

from app.repositories.comments import CommentRepository
from app.repositories.notifications import NotificationRepository
from app.services.comments import CommentService
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


def _make_service(db_session) -> CommentService:
    return CommentService(
        CommentRepository(db_session), NotificationRepository(db_session)
    )


async def test_create_top_level_comment(db_session):
    author, _, movie = await _setup(db_session)
    service = _make_service(db_session)

    comment = await service.create_comment(
        author.id, movie.id, "Nice movie!", None
    )
    await db_session.commit()

    assert comment.id is not None
    assert comment.parent_id is None


async def test_create_reply(db_session):
    author, replier, movie = await _setup(db_session)
    service = _make_service(db_session)

    parent = await service.create_comment(
        author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    reply = await service.create_comment(
        replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    assert reply.parent_id == parent.id


async def test_reply_creates_notification(db_session):
    author, replier, movie = await _setup(db_session)
    service = _make_service(db_session)
    notifications = NotificationRepository(db_session)

    parent = await service.create_comment(
        author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await service.create_comment(
        replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    result = await notifications.get_user_notifications(author.id, False)

    assert len(result) == 1
    assert result[0].user_id == author.id


async def test_reply_to_self_no_notification(db_session):
    author, _, movie = await _setup(db_session)
    service = _make_service(db_session)
    notifications = NotificationRepository(db_session)

    parent = await service.create_comment(
        author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await service.create_comment(
        author.id, movie.id, "Self reply", parent.id
    )
    await db_session.commit()

    result = await notifications.get_user_notifications(author.id, False)

    assert len(result) == 0


async def test_get_movie_comments_with_replies(db_session):
    author, replier, movie = await _setup(db_session)
    service = _make_service(db_session)
    comments = CommentRepository(db_session)

    parent = await service.create_comment(
        author.id, movie.id, "Parent", None
    )
    await db_session.commit()

    await service.create_comment(
        replier.id, movie.id, "Reply", parent.id
    )
    await db_session.commit()

    result = await comments.get_movie_comments(movie.id)

    assert len(result) == 1
    assert result[0].id == parent.id
    assert len(result[0].replies) == 1
