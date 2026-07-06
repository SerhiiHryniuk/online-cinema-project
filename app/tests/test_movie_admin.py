from decimal import Decimal

import pytest

from app.crud.movie_admin import (
    create_movie,
    delete_movie,
    get_movie_admin,
    movie_has_purchases,
    update_movie,
)
from app.models.movies import Certification, Genre, Star
from app.models.orders import Order, OrderItem, OrderStatus
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.schemas.movie_admin import (
    MovieCreateSchema,
    MovieUpdateSchema,
)


async def _setup_refs(db_session):
    cert = Certification(name="PG-13")
    genre = Genre(name="Sci-Fi")
    star = Star(name="Lead Actor")
    db_session.add_all([cert, genre, star])
    await db_session.commit()
    return cert, genre, star


def _movie_payload(cert, genre, star):
    return MovieCreateSchema(
        name="Dune",
        year=2021,
        time=155,
        imdb=8.0,
        votes=700000,
        description="A desert planet saga.",
        price=Decimal("12.99"),
        certification_id=cert.id,
        genre_ids=[genre.id],
        star_ids=[star.id],
        director_ids=[],
    )


async def test_create_movie_with_relations(db_session):
    cert, genre, star = await _setup_refs(db_session)

    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()

    loaded = await get_movie_admin(db_session, movie.id)

    assert loaded.name == "Dune"
    assert len(loaded.genres) == 1
    assert len(loaded.stars) == 1


async def test_update_movie(db_session):
    cert, genre, star = await _setup_refs(db_session)
    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()

    await update_movie(
        db_session,
        movie,
        MovieUpdateSchema(name="Dune Part Two", price=Decimal("14.99")),
    )
    await db_session.commit()

    loaded = await get_movie_admin(db_session, movie.id)
    assert loaded.name == "Dune Part Two"
    assert loaded.price == Decimal("14.99")


async def test_delete_movie_without_purchases(db_session):
    cert, genre, star = await _setup_refs(db_session)
    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()
    movie_id = movie.id

    await delete_movie(db_session, movie)
    await db_session.commit()

    loaded = await get_movie_admin(db_session, movie_id)
    assert loaded is None


async def test_movie_has_purchases_false(db_session):
    cert, genre, star = await _setup_refs(db_session)
    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()

    has = await movie_has_purchases(db_session, movie.id)
    assert has is False


async def test_movie_has_purchases_true(db_session):
    cert, genre, star = await _setup_refs(db_session)
    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()

    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    buyer = User(
        email="buyer@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    db_session.add(buyer)
    await db_session.commit()

    order = Order(
        user_id=buyer.id,
        status=OrderStatus.PAID,
        total_amount=Decimal("12.99"),
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        movie_id=movie.id,
        price_at_order=Decimal("12.99"),
    )
    db_session.add(item)
    await db_session.commit()

    has = await movie_has_purchases(db_session, movie.id)
    assert has is True


async def test_create_movie_invalid_certification(db_session):
    await _setup_refs(db_session)

    payload = MovieCreateSchema(
        name="Bad Cert",
        year=2021,
        time=120,
        imdb=7.0,
        votes=1000,
        description="Movie with bad certification.",
        price=Decimal("9.99"),
        certification_id=999,
        genre_ids=[],
        star_ids=[],
        director_ids=[],
    )

    with pytest.raises(ValueError):
        await create_movie(db_session, payload)


async def test_create_movie_invalid_genre(db_session):
    cert, _, _ = await _setup_refs(db_session)

    payload = MovieCreateSchema(
        name="Bad Genre",
        year=2021,
        time=120,
        imdb=7.0,
        votes=1000,
        description="Movie with bad genre.",
        price=Decimal("9.99"),
        certification_id=cert.id,
        genre_ids=[999],
        star_ids=[],
        director_ids=[],
    )

    with pytest.raises(ValueError):
        await create_movie(db_session, payload)


async def test_create_movie_invalid_star(db_session):
    cert, _, _ = await _setup_refs(db_session)

    payload = MovieCreateSchema(
        name="Bad Star",
        year=2021,
        time=120,
        imdb=7.0,
        votes=1000,
        description="Movie with bad star.",
        price=Decimal("9.99"),
        certification_id=cert.id,
        genre_ids=[],
        star_ids=[999],
        director_ids=[],
    )

    with pytest.raises(ValueError):
        await create_movie(db_session, payload)


async def test_update_movie_invalid_genre(db_session):
    cert, genre, star = await _setup_refs(db_session)
    movie = await create_movie(
        db_session, _movie_payload(cert, genre, star)
    )
    await db_session.commit()

    with pytest.raises(ValueError):
        await update_movie(
            db_session,
            movie,
            MovieUpdateSchema(genre_ids=[999]),
        )
