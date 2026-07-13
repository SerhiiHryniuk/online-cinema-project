from decimal import Decimal

from app.models.movies import Certification, Movie
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.repositories.favorites import FavoriteRepository

from app.schemas.movies import MovieFilterParams


async def _setup(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="fav@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    cert = Certification(name="PG-13")
    db_session.add_all([user, cert])
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
    matrix = Movie(
        name="The Matrix",
        year=1999,
        time=136,
        imdb=8.7,
        votes=1900000,
        description="A hacker learns the truth about reality.",
        price=Decimal("7.99"),
        certification_id=cert.id,
    )
    db_session.add_all([inception, matrix])
    await db_session.commit()

    return user, inception, matrix


async def test_add_favorite(db_session):
    user, inception, _ = await _setup(db_session)
    repo = FavoriteRepository(db_session)

    favorite = await repo.add(user.id, inception.id)
    await db_session.commit()

    assert favorite.id is not None
    assert favorite.movie_id == inception.id


async def test_remove_favorite(db_session):
    user, inception, _ = await _setup(db_session)
    repo = FavoriteRepository(db_session)

    await repo.add(user.id, inception.id)
    await db_session.commit()

    removed = await repo.remove(user.id, inception.id)
    await db_session.commit()

    assert removed is True

    found = await repo.get(user.id, inception.id)
    assert found is None


async def test_remove_favorite_when_none(db_session):
    user, inception, _ = await _setup(db_session)
    repo = FavoriteRepository(db_session)

    removed = await repo.remove(user.id, inception.id)
    assert removed is False


async def test_favorites_list_only_users_favorites(db_session):
    user, inception, matrix = await _setup(db_session)
    repo = FavoriteRepository(db_session)

    await repo.add(user.id, inception.id)
    await db_session.commit()

    params = MovieFilterParams()
    items, total = await repo.get_favorite_movies_page(user.id, 1, 10, params)

    assert total == 1
    assert items[0].name == "Inception"


async def test_favorites_list_with_search(db_session):
    user, inception, matrix = await _setup(db_session)
    repo = FavoriteRepository(db_session)

    await repo.add(user.id, inception.id)
    await repo.add(user.id, matrix.id)
    await db_session.commit()

    params = MovieFilterParams(search="matrix")
    items, total = await repo.get_favorite_movies_page(user.id, 1, 10, params)

    assert total == 1
    assert items[0].name == "The Matrix"
