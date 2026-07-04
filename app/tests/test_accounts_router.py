from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.core.config import settings
from app.crud.accounts import (
    create_activation_token,
    get_activation_token_by_user_id,
    get_activation_token_with_user,
    get_refresh_token,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel, RefreshTokenModel
from app.routers.accounts import router as accounts_router
from app.security import hash_password
from app.security.tokens import create_access_token, create_refresh_token

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="inactive@example.com",
        hashed_password="hashed",
        group_id=user_group.id,
    )
    db_session.add(u)
    await db_session.commit()
    return u


ACTIVE_USER_PASSWORD = "CorrectPass123"


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="active@example.com",
        hashed_password=hash_password(ACTIVE_USER_PASSWORD),
        group_id=user_group.id,
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


class TestRegisterUser:
    async def test_registers_new_user_and_sends_activation_email(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        user_group: UserGroup,
        send_activation_email_mock: MagicMock,
    ):
        response = await client.post(
            "/accounts/register/",
            json={"email": "new@example.com", "password": "StrongPass123"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new@example.com"
        assert body["is_active"] is False

        send_activation_email_mock.delay.assert_called_once()
        email_arg, link_arg = send_activation_email_mock.delay.call_args.args
        assert email_arg == "new@example.com"

        assert "email=new%40example.com" in link_arg
        assert "token=" in link_arg
        token_value = link_arg.split("token=")[1].split("&")[0]
        assert len(token_value) > 0

    async def test_returns_409_for_duplicate_email(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
    ):
        response = await client.post(
            "/accounts/register/",
            json={"email": inactive_user.email, "password": "StrongPass123"},
        )

        assert response.status_code == 409

    async def test_returns_500_when_default_group_missing(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        response = await client.post(
            "/accounts/register/",
            json={"email": "no-group@example.com", "password": "StrongPass123"},
        )

        assert response.status_code == 500


class TestActivateAccount:
    async def test_activates_user_with_valid_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
        send_activation_complete_email_mock: MagicMock,
    ):
        token = await create_activation_token(db_session, user_id=inactive_user.id)
        await db_session.commit()

        response = await client.post(
            "/accounts/activate/",
            json={"email": inactive_user.email, "token": token.token},
        )

        assert response.status_code == 200
        await db_session.refresh(inactive_user)
        assert inactive_user.is_active is True
        assert await db_session.get(ActivationTokenModel, token.id) is None
        send_activation_complete_email_mock.delay.assert_called_once()

    async def test_rejects_invalid_token(
        self, client: httpx.AsyncClient, db_session: AsyncSession, inactive_user: User
    ):
        await create_activation_token(db_session, user_id=inactive_user.id)
        await db_session.commit()

        response = await client.post(
            "/accounts/activate/",
            json={"email": inactive_user.email, "token": "wrong-token"},
        )

        assert response.status_code == 400

    async def test_rejects_expired_token_and_removes_it(
        self, client: httpx.AsyncClient, db_session: AsyncSession, inactive_user: User
    ):
        expired_token = ActivationTokenModel(
            user_id=inactive_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(expired_token)
        await db_session.commit()
        token_value = expired_token.token
        token_id = expired_token.id

        response = await client.post(
            "/accounts/activate/",
            json={"email": inactive_user.email, "token": token_value},
        )

        assert response.status_code == 400
        assert await db_session.get(ActivationTokenModel, token_id) is None

    async def test_rejects_already_active_user(
        self, client: httpx.AsyncClient, db_session: AsyncSession, inactive_user: User
    ):
        token = await create_activation_token(db_session, user_id=inactive_user.id)
        inactive_user.is_active = True
        await db_session.commit()

        response = await client.post(
            "/accounts/activate/",
            json={"email": inactive_user.email, "token": token.token},
        )

        assert response.status_code == 400


class TestActivateAccountViaLink:
    async def test_activates_user_via_get_link(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
        send_activation_complete_email_mock: MagicMock,
    ):
        token = await create_activation_token(db_session, user_id=inactive_user.id)
        await db_session.commit()

        response = await client.get(
            "/accounts/activate/",
            params={"email": inactive_user.email, "token": token.token},
        )

        assert response.status_code == 200
        await db_session.refresh(inactive_user)
        assert inactive_user.is_active is True
        assert await db_session.get(ActivationTokenModel, token.id) is None
        send_activation_complete_email_mock.delay.assert_called_once()

    async def test_rejects_invalid_token_via_get(
        self, client: httpx.AsyncClient, db_session: AsyncSession, inactive_user: User
    ):
        await create_activation_token(db_session, user_id=inactive_user.id)
        await db_session.commit()

        response = await client.get(
            "/accounts/activate/",
            params={"email": inactive_user.email, "token": "wrong-token"},
        )

        assert response.status_code == 400


class TestResendActivation:
    async def test_issues_new_token_and_sends_email(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
        send_activation_email_mock: MagicMock,
    ):
        old_token = await create_activation_token(db_session, user_id=inactive_user.id)
        await db_session.commit()
        old_token_value = old_token.token

        response = await client.post(
            "/accounts/resend-activation/",
            json={"email": inactive_user.email},
        )

        assert response.status_code == 200

        stale_lookup = await get_activation_token_with_user(
            db_session, email=inactive_user.email, token=old_token_value
        )
        assert stale_lookup is None

        new_token = await get_activation_token_by_user_id(db_session, inactive_user.id)
        assert new_token is not None
        assert new_token.token != old_token_value

        send_activation_email_mock.delay.assert_called_once()
        email_arg, link_arg = send_activation_email_mock.delay.call_args.args
        assert email_arg == inactive_user.email
        assert f"token={new_token.token}" in link_arg
        assert old_token_value not in link_arg

    async def test_returns_404_for_unknown_email(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        response = await client.post(
            "/accounts/resend-activation/",
            json={"email": "missing@example.com"},
        )

        assert response.status_code == 404

    async def test_returns_400_for_already_active_user(
        self, client: httpx.AsyncClient, db_session: AsyncSession, inactive_user: User
    ):
        inactive_user.is_active = True
        await db_session.commit()

        response = await client.post(
            "/accounts/resend-activation/",
            json={"email": inactive_user.email},
        )

        assert response.status_code == 400


class TestLogin:
    async def test_returns_token_pair_for_valid_credentials(
        self, client: httpx.AsyncClient, active_user: User
    ):
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": ACTIVE_USER_PASSWORD},
        )

        assert response.status_code == 201
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_creates_refresh_token_record_in_db(
        self, client: httpx.AsyncClient, db_session: AsyncSession, active_user: User
    ):
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": ACTIVE_USER_PASSWORD},
        )

        refresh_token_value = response.json()["refresh_token"]
        record = await get_refresh_token(db_session, refresh_token_value)

        assert record is not None
        assert record.user_id == active_user.id

    async def test_access_token_has_shorter_ttl_than_refresh_token(
        self, client: httpx.AsyncClient, active_user: User
    ):
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": ACTIVE_USER_PASSWORD},
        )
        body = response.json()

        access_decoded = jwt.decode(
            body["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        refresh_decoded = jwt.decode(
            body["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        assert access_decoded["type"] == "access"
        assert refresh_decoded["type"] == "refresh"
        assert access_decoded["exp"] < refresh_decoded["exp"]

    async def test_rejects_wrong_password(
        self, client: httpx.AsyncClient, active_user: User
    ):
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": "WrongPassword1"},
        )

        assert response.status_code == 401

    async def test_rejects_unknown_email(self, client: httpx.AsyncClient):
        response = await client.post(
            "/accounts/login/",
            json={"email": "unknown@example.com", "password": "WhateverPass1"},
        )

        assert response.status_code == 401

    async def test_rejects_inactive_user(
        self, client: httpx.AsyncClient, db_session: AsyncSession, user_group: UserGroup
    ):
        inactive = User(
            email="inactive-login@example.com",
            hashed_password=hash_password(ACTIVE_USER_PASSWORD),
            group_id=user_group.id,
            is_active=False,
        )
        db_session.add(inactive)
        await db_session.commit()

        response = await client.post(
            "/accounts/login/",
            json={"email": inactive.email, "password": ACTIVE_USER_PASSWORD},
        )

        assert response.status_code == 403


class TestRefresh:
    async def _login(self, client: httpx.AsyncClient, active_user: User) -> dict:
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": ACTIVE_USER_PASSWORD},
        )
        return response.json()

    async def test_returns_new_token_pair(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await self._login(client, active_user)

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 200
        new_tokens = response.json()
        assert new_tokens["refresh_token"] != tokens["refresh_token"]
        assert new_tokens["access_token"] != tokens["access_token"]

    async def test_rotates_refresh_token_in_db(
        self, client: httpx.AsyncClient, db_session: AsyncSession, active_user: User
    ):
        tokens = await self._login(client, active_user)

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        new_refresh_token = response.json()["refresh_token"]

        assert await get_refresh_token(db_session, tokens["refresh_token"]) is None
        record = await get_refresh_token(db_session, new_refresh_token)
        assert record is not None
        assert record.user_id == active_user.id

    async def test_old_refresh_token_cannot_be_reused(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await self._login(client, active_user)

        first = await client.post(
            "/accounts/refresh/", json={"refresh_token": tokens["refresh_token"]}
        )
        assert first.status_code == 200

        second = await client.post(
            "/accounts/refresh/", json={"refresh_token": tokens["refresh_token"]}
        )
        assert second.status_code == 401

    async def test_rejects_malformed_token(self, client: httpx.AsyncClient):
        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": "not-a-real-token"},
        )

        assert response.status_code == 400

    async def test_rejects_access_token_used_as_refresh_token(
        self, client: httpx.AsyncClient, active_user: User
    ):
        access_token = create_access_token(user_id=active_user.id)

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 400

    async def test_rejects_valid_jwt_not_persisted_in_db(
        self, client: httpx.AsyncClient, active_user: User
    ):
        never_stored_refresh_token = create_refresh_token(user_id=active_user.id)

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": never_stored_refresh_token},
        )

        assert response.status_code == 401

    async def test_rejects_expired_refresh_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        active_user: User,
    ):
        expired_jwt = create_refresh_token(
            user_id=active_user.id, expires_delta=timedelta(seconds=-1)
        )
        db_session.add(RefreshTokenModel(user_id=active_user.id, token=expired_jwt))
        await db_session.commit()

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": expired_jwt},
        )

        assert response.status_code == 400


class TestLogout:
    async def _login(self, client: httpx.AsyncClient, active_user: User) -> dict:
        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": ACTIVE_USER_PASSWORD},
        )
        return response.json()

    async def test_logout_deletes_refresh_token(
        self, client: httpx.AsyncClient, db_session: AsyncSession, active_user: User
    ):
        tokens = await self._login(client, active_user)

        response = await client.post(
            "/accounts/logout/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == 204
        assert await get_refresh_token(db_session, tokens["refresh_token"]) is None

    async def test_logout_without_credentials_is_rejected(
        self, client: httpx.AsyncClient
    ):
        response = await client.post("/accounts/logout/")

        assert response.status_code in (401, 403)

    async def test_logout_with_invalid_access_token_is_rejected(
        self, client: httpx.AsyncClient
    ):
        response = await client.post(
            "/accounts/logout/",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.status_code == 401

    async def test_logout_called_twice_fails_second_time(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await self._login(client, active_user)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        first = await client.post("/accounts/logout/", headers=headers)
        assert first.status_code == 204

        second = await client.post("/accounts/logout/", headers=headers)
        assert second.status_code == 401

    async def test_refresh_token_is_unusable_after_logout(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await self._login(client, active_user)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        await client.post("/accounts/logout/", headers=headers)

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 401
