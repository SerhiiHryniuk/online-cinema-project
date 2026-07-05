from typing import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profiles import create_profile
from app.db.session import get_db
from app.exceptions import MinioConnectionError, MinioFileUploadError
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.routers.profiles import router as profiles_router
from app.security import hash_password
from app.security.tokens import create_access_token

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="profile-router@example.com",
        hashed_password=hash_password("CorrectPass123"),
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
def auth_headers(active_user: User) -> dict:
    token = create_access_token(user_id=active_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def upload_avatar_mock(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value="avatars/1/new.jpg")
    monkeypatch.setattr("app.routers.profiles.upload_avatar", mock)
    return mock


@pytest.fixture
def delete_avatar_mock(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr("app.routers.profiles.delete_avatar", mock)
    return mock


@pytest.fixture
def get_avatar_url_mock(monkeypatch) -> AsyncMock:
    async def _fake_get_avatar_url(file_name, expires_in: int = 3600):
        return f"https://minio.local/{file_name}" if file_name else None

    mock = AsyncMock(side_effect=_fake_get_avatar_url)
    monkeypatch.setattr("app.routers.profiles.get_avatar_url", mock)
    return mock


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    upload_avatar_mock: AsyncMock,
    delete_avatar_mock: AsyncMock,
    get_avatar_url_mock: AsyncMock,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = FastAPI()
    app.include_router(profiles_router, prefix="/profiles")

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestGetProfile:
    async def test_creates_empty_profile_when_missing(
        self, client: httpx.AsyncClient, auth_headers: dict, active_user: User
    ):
        response = await client.get("/profiles/me/", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == active_user.id
        assert body["first_name"] is None
        assert body["avatar_url"] is None

    async def test_returns_existing_profile_with_avatar_url(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        active_user: User,
        db_session: AsyncSession,
    ):
        profile = await create_profile(db_session, active_user.id)
        profile.first_name = "Taras"
        profile.avatar = "avatars/1/old.jpg"
        await db_session.commit()

        response = await client.get("/profiles/me/", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["first_name"] == "Taras"
        assert body["avatar_url"] == "https://minio.local/avatars/1/old.jpg"

    async def test_requires_authentication(self, client: httpx.AsyncClient):
        response = await client.get("/profiles/me/")

        assert response.status_code == 401


class TestUpdateProfile:
    async def test_updates_text_fields_without_avatar(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            data={"first_name": "Taras", "last_name": "Shevchenko"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["first_name"] == "Taras"
        assert body["last_name"] == "Shevchenko"
        upload_avatar_mock.assert_not_awaited()

    async def test_rejects_invalid_name(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            data={"first_name": "T4ras123"},
        )

        assert response.status_code == 422
        upload_avatar_mock.assert_not_awaited()

    async def test_rejects_birth_date_in_the_future(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            data={"date_of_birth": "2999-01-01"},
        )

        assert response.status_code == 422

    async def test_uploads_and_replaces_avatar(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict,
        active_user: User,
        db_session: AsyncSession,
        upload_avatar_mock: AsyncMock,
        delete_avatar_mock: AsyncMock,
    ):
        profile = await create_profile(db_session, active_user.id)
        profile.avatar = "avatars/1/old.jpg"
        await db_session.commit()

        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            files={"avatar": ("new.jpg", b"binary-data", "image/jpeg")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["avatar_url"] == "https://minio.local/avatars/1/new.jpg"
        upload_avatar_mock.assert_awaited_once()
        delete_avatar_mock.assert_awaited_once_with("avatars/1/old.jpg")

    async def test_rejects_unsupported_avatar_type(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            files={"avatar": ("virus.exe", b"data", "application/octet-stream")},
        )

        assert response.status_code == 422
        upload_avatar_mock.assert_not_awaited()

    async def test_rejects_avatar_that_is_too_large(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        oversized = b"0" * (5 * 1024 * 1024 + 1)

        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            files={"avatar": ("big.jpg", oversized, "image/jpeg")},
        )

        assert response.status_code == 422
        upload_avatar_mock.assert_not_awaited()

    async def test_returns_503_when_storage_unreachable(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        upload_avatar_mock.side_effect = MinioConnectionError("boom")

        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            files={"avatar": ("new.jpg", b"data", "image/jpeg")},
        )

        assert response.status_code == 503

    async def test_returns_502_when_upload_fails(
        self, client: httpx.AsyncClient, auth_headers: dict, upload_avatar_mock: AsyncMock
    ):
        upload_avatar_mock.side_effect = MinioFileUploadError("boom")

        response = await client.put(
            "/profiles/me/",
            headers=auth_headers,
            files={"avatar": ("new.jpg", b"data", "image/jpeg")},
        )

        assert response.status_code == 502

    async def test_requires_authentication(self, client: httpx.AsyncClient):
        response = await client.put("/profiles/me/", data={"first_name": "Taras"})

        assert response.status_code == 401
