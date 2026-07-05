from typing import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.routers.accounts import router as accounts_router
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
async def moderator_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.MODERATOR)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def admin_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.ADMIN)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def plain_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="plain@example.com",
        hashed_password=hash_password("Whatever123$"),
        group_id=user_group.id,
        is_active=False,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def moderator_user(db_session: AsyncSession, moderator_group: UserGroup) -> User:
    u = User(
        email="moderator@example.com",
        hashed_password=hash_password("Whatever123$"),
        group_id=moderator_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, admin_group: UserGroup) -> User:
    u = User(
        email="admin@example.com",
        hashed_password=hash_password("Whatever123$"),
        group_id=admin_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
def send_activation_email_mock(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("app.routers.accounts.send_activation_email_task", mock)
    return mock


@pytest.fixture
def send_activation_complete_email_mock(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("app.routers.accounts.send_activation_complete_email_task", mock)
    return mock


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    send_activation_email_mock: MagicMock,
    send_activation_complete_email_mock: MagicMock,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = FastAPI()
    app.include_router(accounts_router, prefix="/accounts")

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def _auth_headers(user: User) -> dict:
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


class TestChangeUserPermissions:
    async def test_rejects_request_without_credentials(
        self, client: httpx.AsyncClient, plain_user: User
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"is_active": True},
        )

        assert response.status_code in (401, 403)

    async def test_rejects_regular_user(
        self, client: httpx.AsyncClient, plain_user: User
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"is_active": True},
            headers=_auth_headers(plain_user),
        )

        assert response.status_code == 403

    async def test_rejects_moderator(
        self,
        client: httpx.AsyncClient,
        moderator_user: User,
        plain_user: User,
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"is_active": True},
            headers=_auth_headers(moderator_user),
        )

        assert response.status_code == 403

    async def test_rejects_invalid_access_token(
        self, client: httpx.AsyncClient, plain_user: User
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"is_active": True},
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.status_code == 401


class TestChangeUserActivation:
    async def test_admin_activates_user(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        plain_user: User,
    ):
        assert plain_user.is_active is False

        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"is_active": True},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is True
        assert body["id"] == plain_user.id

        await db_session.refresh(plain_user)
        assert plain_user.is_active is True

    async def test_admin_deactivates_user(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        moderator_user: User,
    ):
        assert moderator_user.is_active is True

        response = await client.post(
            f"/accounts/users/{moderator_user.id}/change-user",
            json={"is_active": False},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

        await db_session.refresh(moderator_user)
        assert moderator_user.is_active is False

    async def test_partial_update_does_not_touch_group(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        moderator_user: User,
    ):
        response = await client.post(
            f"/accounts/users/{moderator_user.id}/change-user",
            json={"is_active": False},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 200
        assert response.json()["group"] == UserGroupEnum.MODERATOR.value

        await db_session.refresh(moderator_user, attribute_names=["group"])
        assert moderator_user.group.name == UserGroupEnum.MODERATOR


class TestChangeUserGroup:
    async def test_admin_changes_user_group(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        plain_user: User,
        moderator_group: UserGroup,
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"group": UserGroupEnum.MODERATOR.value},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["group"] == UserGroupEnum.MODERATOR.value

        await db_session.refresh(plain_user, attribute_names=["group"])
        assert plain_user.group.name == UserGroupEnum.MODERATOR

    async def test_admin_changes_group_and_activates_together(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        plain_user: User,
        moderator_group: UserGroup,
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"group": UserGroupEnum.MODERATOR.value, "is_active": True},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["group"] == UserGroupEnum.MODERATOR.value
        assert body["is_active"] is True

        await db_session.refresh(plain_user, attribute_names=["group"])
        assert plain_user.group.name == UserGroupEnum.MODERATOR
        assert plain_user.is_active is True

    async def test_rejects_group_that_does_not_exist_in_db(
        self,
        client: httpx.AsyncClient,
        admin_user: User,
        plain_user: User,
    ):
        response = await client.post(
            f"/accounts/users/{plain_user.id}/change-user",
            json={"group": UserGroupEnum.MODERATOR.value},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 404


class TestChangeUserNotFound:
    async def test_returns_404_for_missing_user(
        self, client: httpx.AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/accounts/users/999999/change-user",
            json={"is_active": True},
            headers=_auth_headers(admin_user),
        )

        assert response.status_code == 404
