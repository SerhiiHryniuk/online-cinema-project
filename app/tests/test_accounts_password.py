from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.tokens import PasswordResetTokenRepository, RefreshTokenRepository
from app.db.session import get_db
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import PasswordResetTokenModel
from app.routers.accounts import router as accounts_router
from app.security import hash_password, verify_password

pytestmark = pytest.mark.asyncio

OLD_PASSWORD = "OldPass123$"
NEW_PASSWORD = "NewPass456$"


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="active@example.com",
        hashed_password=hash_password(OLD_PASSWORD),
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="inactive@example.com",
        hashed_password=hash_password(OLD_PASSWORD),
        group_id=user_group.id,
        is_active=False,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
def password_reset_tokens(db_session: AsyncSession) -> PasswordResetTokenRepository:
    return PasswordResetTokenRepository(db_session)


@pytest.fixture
def refresh_tokens(db_session: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(db_session)


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


@pytest.fixture
def send_password_reset_email_mock(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("app.routers.accounts.send_password_reset_email_task", mock)
    return mock


@pytest.fixture
def send_password_reset_complete_email_mock(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("app.routers.accounts.send_password_reset_complete_email_task", mock)
    return mock


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    send_activation_email_mock: MagicMock,
    send_activation_complete_email_mock: MagicMock,
    send_password_reset_email_mock: MagicMock,
    send_password_reset_complete_email_mock: MagicMock,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = FastAPI()
    app.include_router(accounts_router, prefix="/accounts")

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _login(client: httpx.AsyncClient, user: User, password: str = OLD_PASSWORD) -> dict:
    response = await client.post(
        "/accounts/login/",
        json={"email": user.email, "password": password},
    )
    return response.json()


class TestChangePassword:
    async def test_requires_authentication(self, client: httpx.AsyncClient):
        response = await client.post(
            "/accounts/change-password/",
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code in (401, 403)

    async def test_rejects_invalid_access_token(self, client: httpx.AsyncClient):
        response = await client.post(
            "/accounts/change-password/",
            headers={"Authorization": "Bearer not-a-real-token"},
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 401

    async def test_changes_password_with_correct_old_password(
        self, client: httpx.AsyncClient, db_session: AsyncSession, active_user: User
    ):
        tokens = await _login(client, active_user)

        response = await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 200
        await db_session.refresh(active_user)
        assert verify_password(NEW_PASSWORD, active_user.hashed_password)
        assert not verify_password(OLD_PASSWORD, active_user.hashed_password)

    async def test_can_login_with_new_password_after_change(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await _login(client, active_user)

        await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        old_login = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": OLD_PASSWORD},
        )
        new_login = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": NEW_PASSWORD},
        )

        assert old_login.status_code == 401
        assert new_login.status_code == 201

    async def test_invalidates_existing_refresh_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        refresh_tokens: RefreshTokenRepository,
        active_user: User,
    ):
        tokens = await _login(client, active_user)

        await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 401
        assert await refresh_tokens.get_by_user_id(active_user.id) is None

    async def test_rejects_wrong_old_password(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await _login(client, active_user)

        response = await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": "WrongOldPass123$",
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 400

    async def test_rejects_mismatched_password_confirmation(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await _login(client, active_user)

        response = await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": OLD_PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirm": "SomethingElse123$",
            },
        )

        assert response.status_code == 422

    async def test_rejects_weak_new_password(
        self, client: httpx.AsyncClient, active_user: User
    ):
        tokens = await _login(client, active_user)

        response = await client.post(
            "/accounts/change-password/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "old_password": OLD_PASSWORD,
                "password": "weakpassword",
                "password_confirm": "weakpassword",
            },
        )

        assert response.status_code == 422


class TestForgotPassword:
    async def test_sends_reset_token_for_active_user(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
        send_password_reset_email_mock: MagicMock,
    ):
        response = await client.post(
            "/accounts/forgot-password/",
            json={"email": active_user.email},
        )

        assert response.status_code == 200

        token_record = await password_reset_tokens.get_by_user_id(active_user.id)
        assert token_record is not None

        send_password_reset_email_mock.delay.assert_called_once()
        email_arg, token_arg = send_password_reset_email_mock.delay.call_args.args
        assert email_arg == active_user.email
        assert token_arg == token_record.token

    async def test_returns_generic_message_for_unknown_email(
        self, client: httpx.AsyncClient, send_password_reset_email_mock: MagicMock
    ):
        response = await client.post(
            "/accounts/forgot-password/",
            json={"email": "missing@example.com"},
        )

        assert response.status_code == 200
        send_password_reset_email_mock.delay.assert_not_called()

    async def test_does_not_send_reset_token_for_inactive_user(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        inactive_user: User,
        send_password_reset_email_mock: MagicMock,
    ):
        response = await client.post(
            "/accounts/forgot-password/",
            json={"email": inactive_user.email},
        )

        assert response.status_code == 200
        assert await password_reset_tokens.get_by_user_id(inactive_user.id) is None
        send_password_reset_email_mock.delay.assert_not_called()

    async def test_unknown_and_inactive_responses_are_identical(
        self, client: httpx.AsyncClient, inactive_user: User
    ):
        unknown_response = await client.post(
            "/accounts/forgot-password/",
            json={"email": "missing@example.com"},
        )
        inactive_response = await client.post(
            "/accounts/forgot-password/",
            json={"email": inactive_user.email},
        )

        assert unknown_response.status_code == inactive_response.status_code
        assert unknown_response.json() == inactive_response.json()

    async def test_repeated_request_replaces_old_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
        send_password_reset_email_mock: MagicMock,
    ):
        await client.post(
            "/accounts/forgot-password/", json={"email": active_user.email}
        )
        first_token = await password_reset_tokens.get_by_user_id(active_user.id)
        first_token_value = first_token.token

        await client.post(
            "/accounts/forgot-password/", json={"email": active_user.email}
        )
        second_token = await password_reset_tokens.get_by_user_id(active_user.id)

        assert second_token.token != first_token_value

        stale_lookup = await db_session.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.token == first_token_value
            )
        )
        assert stale_lookup.scalar_one_or_none() is None

        assert send_password_reset_email_mock.delay.call_count == 2


class TestResetPassword:
    async def test_resets_password_with_valid_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
        send_password_reset_complete_email_mock: MagicMock,
    ):
        token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        response = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 200
        await db_session.refresh(active_user)
        assert verify_password(NEW_PASSWORD, active_user.hashed_password)
        assert await db_session.get(PasswordResetTokenModel, token.id) is None
        send_password_reset_complete_email_mock.delay.assert_called_once()

    async def test_can_login_with_new_password_after_reset(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
    ):
        token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        response = await client.post(
            "/accounts/login/",
            json={"email": active_user.email, "password": NEW_PASSWORD},
        )

        assert response.status_code == 201

    async def test_invalidates_existing_refresh_token(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        refresh_tokens: RefreshTokenRepository,
        active_user: User,
    ):
        tokens = await _login(client, active_user)
        reset_token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        await client.post(
            "/accounts/reset-password/",
            json={
                "token": reset_token.token,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        response = await client.post(
            "/accounts/refresh/",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert response.status_code == 401
        assert await refresh_tokens.get_by_user_id(active_user.id) is None

    async def test_rejects_invalid_token(self, client: httpx.AsyncClient):
        response = await client.post(
            "/accounts/reset-password/",
            json={
                "token": "wrong-token",
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 400

    async def test_rejects_expired_token_and_removes_it(
        self, client: httpx.AsyncClient, db_session: AsyncSession, active_user: User
    ):
        expired_token = PasswordResetTokenModel(
            user_id=active_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(expired_token)
        await db_session.commit()
        token_value = expired_token.token
        token_id = expired_token.id

        response = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token_value,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )

        assert response.status_code == 400
        assert await db_session.get(PasswordResetTokenModel, token_id) is None

    async def test_token_cannot_be_reused_after_successful_reset(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
    ):
        token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        first = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
            },
        )
        assert first.status_code == 200

        second = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": "AnotherPass789$",
                "password_confirm": "AnotherPass789$",
            },
        )
        assert second.status_code == 400

    async def test_rejects_mismatched_password_confirmation(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
    ):
        token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        response = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": NEW_PASSWORD,
                "password_confirm": "SomethingElse123$",
            },
        )

        assert response.status_code == 422

    async def test_rejects_weak_new_password(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        password_reset_tokens: PasswordResetTokenRepository,
        active_user: User,
    ):
        token = await password_reset_tokens.create(user_id=active_user.id)
        await db_session.commit()

        response = await client.post(
            "/accounts/reset-password/",
            json={
                "token": token.token,
                "password": "weakpassword",
                "password_confirm": "weakpassword",
            },
        )

        assert response.status_code == 422
