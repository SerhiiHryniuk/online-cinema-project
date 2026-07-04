from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.flush()

    u = User(
        email="test@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    group = UserGroup(name=UserGroupEnum.MODERATOR)
    db_session.add(group)
    await db_session.flush()

    u = User(
        email="other@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    db_session.add(u)
    await db_session.commit()
    return u


class TestActivationTokenModel:
    async def test_creates_with_defaults(self, db_session: AsyncSession, user: User):
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        assert token.id is not None
        assert token.token
        assert isinstance(token.token, str)
        assert len(token.token) <= 64

    async def test_expires_at_default_is_24_hours(
        self, db_session: AsyncSession, user: User
    ):
        before = datetime.now(timezone.utc)
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=1)
        expected_max = after + timedelta(days=1)
        assert expected_min <= token.expires_at <= expected_max

    async def test_token_is_unique(
        self, db_session: AsyncSession, user: User, other_user: User
    ):
        fixed_token = "same-token-value"
        db_session.add(ActivationTokenModel(user_id=user.id, token=fixed_token))
        await db_session.commit()

        db_session.add(
            ActivationTokenModel(user_id=other_user.id, token=fixed_token)
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_one_token_per_user(self, db_session: AsyncSession, user: User):
        db_session.add(ActivationTokenModel(user_id=user.id))
        await db_session.commit()

        db_session.add(ActivationTokenModel(user_id=user.id))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_user_relationship(self, db_session: AsyncSession, user: User):
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(user, attribute_names=["activation_token"])

        assert token.user_id == user.id
        assert user.activation_token.id == token.id

    async def test_cascade_delete_when_user_removed(
        self, db_session: AsyncSession, user: User
    ):
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        token_id = token.id

        await db_session.delete(user)
        await db_session.commit()

        assert await db_session.get(ActivationTokenModel, token_id) is None

    async def test_repr(self, db_session: AsyncSession, user: User):
        token = ActivationTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        assert "ActivationTokenModel" in repr(token)
        assert str(token.id) in repr(token)


class TestPasswordResetTokenModel:
    async def test_creates_with_defaults(self, db_session: AsyncSession, user: User):
        token = PasswordResetTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        assert token.id is not None
        assert token.token
        assert token.expires_at > datetime.now(timezone.utc)

    async def test_one_token_per_user(self, db_session: AsyncSession, user: User):
        db_session.add(PasswordResetTokenModel(user_id=user.id))
        await db_session.commit()

        db_session.add(PasswordResetTokenModel(user_id=user.id))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_token_is_unique_across_users(
        self, db_session: AsyncSession, user: User, other_user: User
    ):
        fixed_token = "shared-reset-token"
        db_session.add(PasswordResetTokenModel(user_id=user.id, token=fixed_token))
        await db_session.commit()

        db_session.add(
            PasswordResetTokenModel(user_id=other_user.id, token=fixed_token)
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_user_relationship(self, db_session: AsyncSession, user: User):
        token = PasswordResetTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(user, attribute_names=["password_reset_token"])

        assert user.password_reset_token.id == token.id

    async def test_cascade_delete_when_user_removed(
        self, db_session: AsyncSession, user: User
    ):
        token = PasswordResetTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        token_id = token.id

        await db_session.delete(user)
        await db_session.commit()

        assert await db_session.get(PasswordResetTokenModel, token_id) is None


class TestRefreshTokenModel:
    async def test_creates_with_defaults(self, db_session: AsyncSession, user: User):
        token = RefreshTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        assert token.id is not None
        assert token.token
        assert len(token.token) <= 512

    async def test_multiple_tokens_allowed_per_user(
        self, db_session: AsyncSession, user: User
    ):
        t1 = RefreshTokenModel(user_id=user.id)
        t2 = RefreshTokenModel(user_id=user.id)
        db_session.add_all([t1, t2])
        await db_session.commit()

        result = await db_session.execute(
            select(RefreshTokenModel).filter_by(user_id=user.id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 2

    async def test_token_value_is_unique(
        self, db_session: AsyncSession, user: User, other_user: User
    ):
        fixed_token = "same-refresh-token"
        db_session.add(RefreshTokenModel(user_id=user.id, token=fixed_token))
        await db_session.commit()

        db_session.add(
            RefreshTokenModel(user_id=other_user.id, token=fixed_token)
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_create_classmethod_sets_expected_fields(
        self, db_session: AsyncSession, user: User
    ):
        before = datetime.now(timezone.utc)
        token = RefreshTokenModel.create(
            user_id=user.id, days_valid=7, token="custom-token"
        )
        after = datetime.now(timezone.utc)

        assert token.user_id == user.id
        assert token.token == "custom-token"
        assert (
            before + timedelta(days=7)
            <= token.expires_at
            <= after + timedelta(days=7)
        )

        db_session.add(token)
        await db_session.commit()
        assert token.id is not None

    async def test_create_classmethod_different_days_valid(self, user: User):
        short_lived = RefreshTokenModel.create(
            user_id=user.id, days_valid=1, token="short"
        )
        long_lived = RefreshTokenModel.create(
            user_id=user.id, days_valid=30, token="long"
        )
        assert short_lived.expires_at < long_lived.expires_at

    async def test_user_relationship(self, db_session: AsyncSession, user: User):
        token = RefreshTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(user, attribute_names=["refresh_tokens"])

        assert len(user.refresh_tokens) == 1
        assert user.refresh_tokens[0].id == token.id

    async def test_cascade_delete_when_user_removed(
        self, db_session: AsyncSession, user: User
    ):
        t1 = RefreshTokenModel(user_id=user.id)
        t2 = RefreshTokenModel(user_id=user.id)
        db_session.add_all([t1, t2])
        await db_session.commit()
        ids = [t1.id, t2.id]

        await db_session.delete(user)
        await db_session.commit()

        for tid in ids:
            assert await db_session.get(RefreshTokenModel, tid) is None

    async def test_repr(self, db_session: AsyncSession, user: User):
        token = RefreshTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        assert "RefreshTokenModel" in repr(token)
        assert str(token.id) in repr(token)


@pytest.mark.parametrize(
    "model_cls",
    [ActivationTokenModel, PasswordResetTokenModel, RefreshTokenModel],
)
async def test_user_id_required(db_session: AsyncSession, model_cls):
    token = model_cls()
    db_session.add(token)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.parametrize(
    "model_cls",
    [ActivationTokenModel, PasswordResetTokenModel, RefreshTokenModel],
)
async def test_token_auto_generated_when_not_provided(
    db_session: AsyncSession, user: User, model_cls
):
    token = model_cls(user_id=user.id)
    db_session.add(token)
    await db_session.commit()

    assert token.token is not None
    assert len(token.token) > 0
