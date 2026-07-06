from decimal import Decimal

from app.crud.movies import get_movies_page
from app.models.movies import Certification, Movie
from app.schemas.movies import (
    MovieFilterParams,
    MovieSortField,
    MovieSortOrder,
)


async def _make_movies(db_session):
    cert = Certification(name="PG-13")
    db_session.add(cert)
    await db_session.commit()

    movies = [
        Movie(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=2000000,
            description="A thief who steals corporate secrets.",
            price=Decimal("9.99"),
            certification_id=cert.id,
        ),
        Movie(
            name="The Matrix",
            year=1999,
            time=136,
            imdb=8.7,
            votes=1900000,
            description="A hacker learns the truth about reality.",
            price=Decimal("7.99"),
            certification_id=cert.id,
        ),
        Movie(
            name="Interstellar",
            year=2014,
            time=169,
            imdb=8.7,
            votes=1800000,
            description="Explorers travel through a wormhole.",
            price=Decimal("11.99"),
            certification_id=cert.id,
        ),
    ]
    db_session.add_all(movies)
    await db_session.commit()


async def test_no_filters_returns_all(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams()

    items, total = await get_movies_page(db_session, 1, 10, params)

    assert total == 3
    assert len(items) == 3


async def test_filter_by_year(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams(year=2010)

    items, total = await get_movies_page(db_session, 1, 10, params)

    assert total == 1
    assert items[0].name == "Inception"


async def test_filter_by_min_imdb(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams(min_imdb=8.8)

    items, total = await get_movies_page(db_session, 1, 10, params)

    assert total == 1
    assert items[0].name == "Inception"


async def test_search_by_name(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams(search="matrix")

    items, total = await get_movies_page(db_session, 1, 10, params)

    assert total == 1
    assert items[0].name == "The Matrix"


async def test_search_by_description(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams(search="wormhole")

    items, total = await get_movies_page(db_session, 1, 10, params)

    assert total == 1
    assert items[0].name == "Interstellar"


async def test_sort_by_price_asc(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams(
        sort_by=MovieSortField.PRICE,
        sort_order=MovieSortOrder.ASC,
    )

    items, total = await get_movies_page(db_session, 1, 10, params)

    prices = [item.price for item in items]
    assert prices == sorted(prices)


async def test_pagination(db_session):
    await _make_movies(db_session)
    params = MovieFilterParams()

    items, total = await get_movies_page(db_session, 1, 2, params)

    assert total == 3
    assert len(items) == 2
