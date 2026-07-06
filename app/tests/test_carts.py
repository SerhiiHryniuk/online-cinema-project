from decimal import Decimal
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.models.accounts import User, UserGroup
from app.models.movies import Movie, Certification, Genre
from app.routers.carts import router as carts_router
from app.security import hash_password
from app.security.tokens import create_access_token

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name="USER")
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest_asyncio.fixture
async def admin_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name="ADMIN")
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest_asyncio.fixture
async def active_user(
    db_session: AsyncSession, user_group: UserGroup
) -> User:
    u = User(
        email="user-cart@example.com",
        hashed_password=hash_password("CorrectPass123"),
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def admin_user(
    db_session: AsyncSession, admin_group: UserGroup
) -> User:
    u = User(
        email="admin-cart@example.com",
        hashed_password=hash_password("AdminPass123"),
        group_id=admin_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def certification(db_session: AsyncSession) -> Certification:
    cert = Certification(name="PG-13")
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)
    return cert


@pytest_asyncio.fixture
async def sci_fi_genre(db_session: AsyncSession) -> Genre:
    genre = Genre(name="Sci-Fi")
    db_session.add(genre)
    await db_session.commit()
    await db_session.refresh(genre)
    return genre


@pytest_asyncio.fixture
async def action_genre(db_session: AsyncSession) -> Genre:
    genre = Genre(name="Action")
    db_session.add(genre)
    await db_session.commit()
    await db_session.refresh(genre)
    return genre


@pytest_asyncio.fixture
async def thriller_genre(db_session: AsyncSession) -> Genre:
    genre = Genre(name="Thriller")
    db_session.add(genre)
    await db_session.commit()
    await db_session.refresh(genre)
    return genre


@pytest.fixture
def auth_headers(active_user: User) -> dict:
    token = create_access_token(user_id=active_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user: User) -> dict:
    token = create_access_token(user_id=admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(carts_router, prefix="/carts")

    from app.db.session import get_db

    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


class TestCartOperations:
    async def test_get_empty_cart_creates_new_one(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        response = await client.get("/carts/me", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert "id" in body
        assert body["items"] == []

    async def test_add_movie_to_cart_success(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        certification: Certification,
        sci_fi_genre: Genre,
    ):
        movie = Movie(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=2000000,
            description="A thief who steals corporate secrets...",
            price=Decimal("9.99"),
            certification_id=certification.id,
            genres=[sci_fi_genre],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        response = await client.post(
            f"/carts/me/items/{movie.id}", headers=auth_headers
        )

        assert response.status_code == 200

        db_session.expire_all()
        get_response = await client.get("/carts/me", headers=auth_headers)
        body = get_response.json()
        assert len(body["items"]) == 1

        movie_data = body["items"][0]["movie"]
        assert movie_data["name"] == "Inception"
        assert movie_data["year"] == 2010

    async def test_add_duplicate_movie_raises_bad_request(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        certification: Certification,
        sci_fi_genre: Genre,
    ):
        movie = Movie(
            name="The Matrix",
            year=1999,
            time=136,
            imdb=8.7,
            votes=1800000,
            description="A computer hacker learns...",
            price=Decimal("7.99"),
            certification_id=certification.id,
            genres=[sci_fi_genre],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        await client.post(f"/carts/me/items/{movie.id}", headers=auth_headers)

        response = await client.post(
            f"/carts/me/items/{movie.id}", headers=auth_headers
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Movie is already in your cart."

    async def test_remove_movie_from_cart(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        certification: Certification,
        action_genre: Genre,
    ):
        movie = Movie(
            name="Gladiator",
            year=2000,
            time=155,
            imdb=8.5,
            votes=1500000,
            description="A former Roman General...",
            price=Decimal("5.99"),
            certification_id=certification.id,
            genres=[action_genre],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        await client.post(f"/carts/me/items/{movie.id}", headers=auth_headers)
        await db_session.commit()

        delete_response = await client.delete(
            f"/carts/me/items/{movie.id}", headers=auth_headers
        )
        assert delete_response.status_code == 200

        await db_session.commit()

        get_response = await client.get("/carts/me", headers=auth_headers)
        assert len(get_response.json()["items"]) == 0

    async def test_clear_cart(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        certification: Certification,
        thriller_genre: Genre,
    ):
        movie = Movie(
            name="Seven",
            year=1995,
            time=127,
            imdb=8.6,
            votes=1600000,
            description="Two detectives, a rookie and a veteran...",
            price=Decimal("6.99"),
            certification_id=certification.id,
            genres=[thriller_genre],
        )
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        await client.post(f"/carts/me/items/{movie.id}", headers=auth_headers)

        db_session.expire_all()
        response = await client.delete("/carts/me/clear", headers=auth_headers)
        assert response.status_code == 204

        db_session.expire_all()
        get_response = await client.get("/carts/me", headers=auth_headers)
        assert len(get_response.json()["items"]) == 0

    async def test_checkout_empty_cart_raises_not_found(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        response = await client.post("/carts/me/checkout", headers=auth_headers)

        assert response.status_code == 404

    async def test_admin_can_view_user_cart(
        self,
        client: httpx.AsyncClient,
        admin_auth_headers: dict,
        active_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        stmt = (
            select(User)
            .where(User.id == admin_user.id)
            .options(selectinload(User.group))
        )
        await db_session.execute(stmt)

        response = await client.get(
            f"/carts/user/{active_user.id}", headers=admin_auth_headers
        )

        assert response.status_code == 200
        assert "items" in response.json()
