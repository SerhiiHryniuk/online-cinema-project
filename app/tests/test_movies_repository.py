from decimal import Decimal

import pytest

from app.models.orders import Order, OrderItem, OrderStatus
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.movies import Certification, Genre, Star
from app.repositories.movies import MovieRepository
from app.schemas.movie_admin import MovieCreateSchema, MovieUpdateSchema
from app.schemas.movies import MovieFilterParams, MovieSortField, MovieSortOrder


class TestMoviePage:
    async def _seed(self, db_session):
        from app.models.movies import Movie
        cert = Certification(name="PG-13")
        db_session.add(cert)
        await db_session.commit()

        movies = [
            Movie(name="Inception", year=2010, time=148, imdb=8.8, votes=2000000,
                  description="A thief who steals corporate secrets.",
                  price=Decimal("9.99"), certification_id=cert.id),
            Movie(name="The Matrix", year=1999, time=136, imdb=8.7, votes=1900000,
                  description="A hacker learns the truth about reality.",
                  price=Decimal("7.99"), certification_id=cert.id),
            Movie(name="Interstellar", year=2014, time=169, imdb=8.7, votes=1800000,
                  description="Explorers travel through a wormhole.",
                  price=Decimal("11.99"), certification_id=cert.id),
        ]
        db_session.add_all(movies)
        await db_session.commit()

    async def test_no_filters_returns_all(self, db_session):
        await self._seed(db_session)
        repo = MovieRepository(db_session)
        params = MovieFilterParams()

        items, total = await repo.get_page(1, 10, params)

        assert total == 3
        assert len(items) == 3

    async def test_filter_by_year(self, db_session):
        await self._seed(db_session)
        repo = MovieRepository(db_session)
        params = MovieFilterParams(year=2010)

        items, total = await repo.get_page(1, 10, params)

        assert total == 1
        assert items[0].name == "Inception"

    async def test_search_by_name(self, db_session):
        await self._seed(db_session)
        repo = MovieRepository(db_session)
        params = MovieFilterParams(search="matrix")

        items, total = await repo.get_page(1, 10, params)

        assert total == 1
        assert items[0].name == "The Matrix"

    async def test_sort_by_price_asc(self, db_session):
        await self._seed(db_session)
        repo = MovieRepository(db_session)
        params = MovieFilterParams(sort_by=MovieSortField.PRICE, sort_order=MovieSortOrder.ASC)

        items, total = await repo.get_page(1, 10, params)

        prices = [item.price for item in items]
        assert prices == sorted(prices)

    async def test_pagination(self, db_session):
        await self._seed(db_session)
        repo = MovieRepository(db_session)
        params = MovieFilterParams()

        items, total = await repo.get_page(1, 2, params)

        assert total == 3
        assert len(items) == 2


class TestMovieAdmin:
    async def _setup_refs(self, db_session):
        cert = Certification(name="PG-13")
        genre = Genre(name="Sci-Fi")
        star = Star(name="Lead Actor")
        db_session.add_all([cert, genre, star])
        await db_session.commit()
        return cert, genre, star

    def _payload(self, cert, genre, star):
        return MovieCreateSchema(
            name="Dune", year=2021, time=155, imdb=8.0, votes=700000,
            description="A desert planet saga.", price=Decimal("12.99"),
            certification_id=cert.id, genre_ids=[genre.id],
            star_ids=[star.id], director_ids=[],
        )

    async def test_create_movie_with_relations(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)

        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()

        loaded = await repo.get_admin(movie.id)
        assert loaded.name == "Dune"
        assert len(loaded.genres) == 1
        assert len(loaded.stars) == 1

    async def test_update_movie(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)
        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()

        await repo.update(
            movie, MovieUpdateSchema(name="Dune Part Two", price=Decimal("14.99"))
        )
        await db_session.commit()

        loaded = await repo.get_admin(movie.id)
        assert loaded.name == "Dune Part Two"
        assert loaded.price == Decimal("14.99")

    async def test_delete_movie_without_purchases(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)
        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()
        movie_id = movie.id

        await repo.delete(movie)
        await db_session.commit()

        assert await repo.get_admin(movie_id) is None

    async def test_movie_has_purchases_false(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)
        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()

        assert await repo.has_purchases(movie.id) is False

    async def test_movie_has_purchases_true(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)
        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()

        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.commit()

        buyer = User(email="buyer@example.com", hashed_password="hashed", group_id=group.id)
        db_session.add(buyer)
        await db_session.commit()

        order = Order(user_id=buyer.id, status=OrderStatus.PAID, total_amount=Decimal("12.99"))
        db_session.add(order)
        await db_session.flush()

        item = OrderItem(order_id=order.id, movie_id=movie.id, price_at_order=Decimal("12.99"))
        db_session.add(item)
        await db_session.commit()

        assert await repo.has_purchases(movie.id) is True

    async def test_create_movie_invalid_certification(self, db_session):
        await self._setup_refs(db_session)
        repo = MovieRepository(db_session)

        payload = MovieCreateSchema(
            name="Bad Cert", year=2021, time=120, imdb=7.0, votes=1000,
            description="Movie with bad certification.", price=Decimal("9.99"),
            certification_id=999, genre_ids=[], star_ids=[], director_ids=[],
        )

        with pytest.raises(ValueError):
            await repo.create(payload)

    async def test_create_movie_invalid_genre(self, db_session):
        cert, _, _ = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)

        payload = MovieCreateSchema(
            name="Bad Genre", year=2021, time=120, imdb=7.0, votes=1000,
            description="Movie with bad genre.", price=Decimal("9.99"),
            certification_id=cert.id, genre_ids=[999], star_ids=[], director_ids=[],
        )

        with pytest.raises(ValueError):
            await repo.create(payload)

    async def test_update_movie_invalid_genre(self, db_session):
        cert, genre, star = await self._setup_refs(db_session)
        repo = MovieRepository(db_session)
        movie = await repo.create(self._payload(cert, genre, star))
        await db_session.commit()

        with pytest.raises(ValueError):
            await repo.update(movie, MovieUpdateSchema(genre_ids=[999]))
