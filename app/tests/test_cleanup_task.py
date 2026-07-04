from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel
from app.tasks import cleanup


class _SessionProxy:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class TestTaskRegistration:
    def test_is_registered_on_the_celery_app(self):
        celery_app.finalize()
        assert (
            "app.tasks.cleanup.delete_expired_activation_tokens" in celery_app.tasks
        )

    def test_exposes_celery_task_api(self):
        assert hasattr(cleanup.delete_expired_activation_tokens, "delay")
        assert hasattr(cleanup.delete_expired_activation_tokens, "apply_async")


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.flush()

    u = User(email="cleanup@example.com", hashed_password="hashed", group_id=group.id)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    group = UserGroup(name=UserGroupEnum.MODERATOR)
    db_session.add(group)
    await db_session.flush()

    u = User(
        email="other-cleanup@example.com", hashed_password="hashed", group_id=group.id
    )
    db_session.add(u)
    await db_session.commit()
    return u


class TestDeleteExpiredActivationTokensLogic:
    async def test_deletes_only_expired_tokens(
        self,
        db_session: AsyncSession,
        user: User,
        other_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ):
        expired_token = ActivationTokenModel(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        valid_token = ActivationTokenModel(
            user_id=other_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add_all([expired_token, valid_token])
        await db_session.commit()
        expired_id, valid_id = expired_token.id, valid_token.id

        monkeypatch.setattr(cleanup, "AsyncSessionLocal", lambda: _SessionProxy(db_session))

        deleted_count = await cleanup._delete_expired_activation_tokens()

        assert deleted_count == 1
        assert await db_session.get(ActivationTokenModel, expired_id) is None
        assert await db_session.get(ActivationTokenModel, valid_id) is not None

    async def test_returns_zero_when_nothing_expired(
        self, db_session: AsyncSession, user: User, monkeypatch: pytest.MonkeyPatch
    ):
        valid_token = ActivationTokenModel(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(valid_token)
        await db_session.commit()

        monkeypatch.setattr(cleanup, "AsyncSessionLocal", lambda: _SessionProxy(db_session))

        deleted_count = await cleanup._delete_expired_activation_tokens()

        assert deleted_count == 0
        assert await db_session.get(ActivationTokenModel, valid_token.id) is not None
