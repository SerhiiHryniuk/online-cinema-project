import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.movies import (
    Genre,
    Star,
    Director,
    Certification,
    Movie,
)


@pytest.mark.asyncio
class TestGenreModel:
    async def test_create_genre(self, db_session):
        genre = Genre(name="Action")
        db_session.add(genre)
        await db_session.commit()

        result = await db_session.execute(select(Genre).where(Genre.name == "Action"))
        saved_genre = result.scalar_one()

        assert saved_genre.id is not None
        assert saved_genre.name == "Action"

    async def test_genre_name_unique(self, db_session):
        db_session.add(Genre(name="Drama"))
        await db_session.commit()

        db_session.add(Genre(name="Drama"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.asyncio
class TestStarModel:
    async def test_create_star(self, db_session):
        star = Star(name="Tom Hanks")
        db_session.add(star)
        await db_session.commit()

        result = await db_session.execute(select(Star).where(Star.name == "Tom Hanks"))
        saved_star = result.scalar_one()

        assert saved_star.id is not None
        assert saved_star.name == "Tom Hanks"

    async def test_star_name_unique(self, db_session):
        db_session.add(Star(name="Meryl Streep"))
        await db_session.commit()

        db_session.add(Star(name="Meryl Streep"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.asyncio
class TestDirectorModel:
    async def test_create_director(self, db_session):
        director = Director(name="Christopher Nolan")
        db_session.add(director)
        await db_session.commit()

        result = await db_session.execute(
            select(Director).where(Director.name == "Christopher Nolan")
        )
        saved_director = result.scalar_one()

        assert saved_director.id is not None
        assert saved_director.name == "Christopher Nolan"

    async def test_director_name_unique(self, db_session):
        db_session.add(Director(name="Quentin Tarantino"))
        await db_session.commit()

        db_session.add(Director(name="Quentin Tarantino"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.asyncio
class TestCertificationModel:
    async def test_create_certification(self, db_session):
        certification = Certification(name="PG-13")
        db_session.add(certification)
        await db_session.commit()

        result = await db_session.execute(
            select(Certification).where(Certification.name == "PG-13")
        )
        saved_certification = result.scalar_one()

        assert saved_certification.id is not None
        assert saved_certification.name == "PG-13"

    async def test_certification_name_unique(self, db_session):
        db_session.add(Certification(name="R"))
        await db_session.commit()

        db_session.add(Certification(name="R"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.asyncio
class TestMovieModel:
    async def _create_certification(self, db_session, name="PG"):
        certification = Certification(name=name)
        db_session.add(certification)
        await db_session.commit()
        await db_session.refresh(certification)
        return certification

    async def test_create_movie(self, db_session):
        certification = await self._create_certification(db_session, "PG-13")

        movie = Movie(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=2000000,
            meta_score=74.0,
            gross=829895144.0,
            description="A thief who steals corporate secrets through dream-sharing technology.",
            price=Decimal("9.99"),
            certification_id=certification.id,
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        assert movie.id is not None
        assert isinstance(movie.uuid, uuid.UUID)
        assert movie.name == "Inception"
        assert movie.certification_id == certification.id
        assert movie.price == Decimal("9.99")

    async def test_movie_requires_certification(self, db_session):
        movie = Movie(
            name="No Certification Movie",
            year=2020,
            time=100,
            imdb=5.0,
            votes=100,
            description="Test movie without certification.",
            price=Decimal("4.99"),
        )
        db_session.add(movie)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_movie_optional_fields_can_be_null(self, db_session):
        certification = await self._create_certification(db_session, "NC-17")

        movie = Movie(
            name="No Meta Score Movie",
            year=2015,
            time=110,
            imdb=6.5,
            votes=5000,
            description="Test movie without meta_score and gross.",
            price=Decimal("2.99"),
            certification_id=certification.id,
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        assert movie.meta_score is None
        assert movie.gross is None

    async def test_movie_unique_name_year_time_constraint(self, db_session):
        certification = await self._create_certification(db_session, "G")

        movie1 = Movie(
            name="Duplicate Movie",
            year=2021,
            time=120,
            imdb=7.0,
            votes=1000,
            description="First instance.",
            price=Decimal("5.99"),
            certification_id=certification.id,
        )
        db_session.add(movie1)
        await db_session.commit()

        movie2 = Movie(
            name="Duplicate Movie",
            year=2021,
            time=120,
            imdb=7.5,
            votes=2000,
            description="Second instance with same name/year/time.",
            price=Decimal("6.99"),
            certification_id=certification.id,
        )
        db_session.add(movie2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_movie_allows_same_name_different_year(self, db_session):
        certification = await self._create_certification(db_session, "PG-1")

        movie1 = Movie(
            name="Remake",
            year=1990,
            time=100,
            imdb=6.0,
            votes=500,
            description="Original.",
            price=Decimal("3.99"),
            certification_id=certification.id,
        )
        movie2 = Movie(
            name="Remake",
            year=2020,
            time=110,
            imdb=7.0,
            votes=1500,
            description="Remake version.",
            price=Decimal("7.99"),
            certification_id=certification.id,
        )
        db_session.add_all([movie1, movie2])
        await db_session.commit()

        result = await db_session.execute(select(Movie).where(Movie.name == "Remake"))
        movies = result.scalars().all()
        assert len(movies) == 2

    async def test_movie_genres_many_to_many(self, db_session):
        certification = await self._create_certification(db_session, "PG-2")
        action = Genre(name="Action-Test")
        thriller = Genre(name="Thriller-Test")
        db_session.add_all([action, thriller])
        await db_session.commit()

        movie = Movie(
            name="Action Thriller Movie",
            year=2019,
            time=130,
            imdb=7.2,
            votes=3000,
            description="Movie with multiple genres.",
            price=Decimal("8.99"),
            certification_id=certification.id,
            genres=[action, thriller],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie, attribute_names=["genres"])

        assert len(movie.genres) == 2
        genre_names = {genre.name for genre in movie.genres}
        assert genre_names == {"Action-Test", "Thriller-Test"}

    async def test_movie_directors_many_to_many(self, db_session):
        certification = await self._create_certification(db_session, "PG-3")
        director1 = Director(name="Director One")
        director2 = Director(name="Director Two")
        db_session.add_all([director1, director2])
        await db_session.commit()

        movie = Movie(
            name="Co-Directed Movie",
            year=2018,
            time=105,
            imdb=6.8,
            votes=2500,
            description="Movie with multiple directors.",
            price=Decimal("6.49"),
            certification_id=certification.id,
            directors=[director1, director2],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie, attribute_names=["directors"])

        assert len(movie.directors) == 2

    async def test_movie_stars_many_to_many(self, db_session):
        certification = await self._create_certification(db_session, "PG-4")
        star1 = Star(name="Star One")
        star2 = Star(name="Star Two")
        db_session.add_all([star1, star2])
        await db_session.commit()

        movie = Movie(
            name="Star Studded Movie",
            year=2022,
            time=140,
            imdb=8.0,
            votes=10000,
            description="Movie with multiple stars.",
            price=Decimal("11.99"),
            certification_id=certification.id,
            stars=[star1, star2],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie, attribute_names=["stars"])

        assert len(movie.stars) == 2

    async def test_genre_movies_backref(self, db_session):
        certification = await self._create_certification(db_session, "PG-5")
        genre = Genre(name="Backref-Test-Genre")
        db_session.add(genre)
        await db_session.commit()

        movie = Movie(
            name="Backref Movie",
            year=2017,
            time=95,
            imdb=6.0,
            votes=1000,
            description="Testing backref access from genre to movies.",
            price=Decimal("4.49"),
            certification_id=certification.id,
            genres=[genre],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(genre, attribute_names=["movies"])

        assert len(genre.movies) == 1
        assert genre.movies[0].name == "Backref Movie"
