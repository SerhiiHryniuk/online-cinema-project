from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.accounts import (
    create_activation_token,
    get_activation_token_by_user_id,
    get_activation_token_with_user,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel
from app.routers.accounts import router as accounts_router

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
