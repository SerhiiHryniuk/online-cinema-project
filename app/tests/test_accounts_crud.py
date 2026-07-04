from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.accounts import (
    activate_user,
    create_activation_token,
    create_user,
    delete_activation_token,
    get_activation_token_by_user_id,
    get_activation_token_with_user,
    get_user_by_email,
    get_user_group_by_name,
)
from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(email="crud@example.com", hashed_password="hashed", group_id=user_group.id)
    db_session.add(u)
    await db_session.commit()
    return u


class TestGetUserByEmail:
    async def test_returns_existing_user(self, db_session: AsyncSession, user: User):
        found = await get_user_by_email(db_session, "crud@example.com")

        assert found is not None
        assert found.id == user.id

    async def test_returns_none_when_missing(self, db_session: AsyncSession):
        assert await get_user_by_email(db_session, "missing@example.com") is None


class TestGetUserGroupByName:
    async def test_returns_existing_group(
        self, db_session: AsyncSession, user_group: UserGroup
    ):
        found = await get_user_group_by_name(db_session, UserGroupEnum.USER)

        assert found is not None
        assert found.id == user_group.id

    async def test_returns_none_when_missing(self, db_session: AsyncSession):
        assert await get_user_group_by_name(db_session, UserGroupEnum.ADMIN) is None


class TestCreateUser:
    async def test_creates_user_with_expected_fields(
        self, db_session: AsyncSession, user_group: UserGroup
    ):
        created = await create_user(
            db_session,
            email="new-user@example.com",
            hashed_password="hashed-pw",
            group_id=user_group.id,
        )
        await db_session.commit()

        assert created.id is not None
        assert created.email == "new-user@example.com"
        assert created.hashed_password == "hashed-pw"
        assert created.is_active is False


class TestActivationTokenCrud:
    async def test_create_activation_token(self, db_session: AsyncSession, user: User):
        token = await create_activation_token(db_session, user_id=user.id)
        await db_session.commit()

        assert token.id is not None
        assert token.user_id == user.id

    async def test_get_activation_token_with_user(
        self, db_session: AsyncSession, user: User
    ):
        token = await create_activation_token(db_session, user_id=user.id)
        await db_session.commit()

        found = await get_activation_token_with_user(
            db_session, email=user.email, token=token.token
        )

        assert found is not None
        assert found.id == token.id
        assert found.user.id == user.id

    async def test_get_activation_token_with_user_returns_none_for_wrong_token(
        self, db_session: AsyncSession, user: User
    ):
        await create_activation_token(db_session, user_id=user.id)
        await db_session.commit()

        found = await get_activation_token_with_user(
            db_session, email=user.email, token="wrong-token"
        )

        assert found is None

    async def test_get_activation_token_by_user_id(
        self, db_session: AsyncSession, user: User
    ):
        token = await create_activation_token(db_session, user_id=user.id)
        await db_session.commit()

        found = await get_activation_token_by_user_id(db_session, user.id)

        assert found is not None
        assert found.id == token.id

    async def test_get_activation_token_by_user_id_returns_none_when_missing(
        self, db_session: AsyncSession, user: User
    ):
        assert await get_activation_token_by_user_id(db_session, user.id) is None

    async def test_delete_activation_token(self, db_session: AsyncSession, user: User):
        token = await create_activation_token(db_session, user_id=user.id)
        await db_session.commit()
        token_id = token.id

        await delete_activation_token(db_session, token)
        await db_session.commit()

        assert await db_session.get(ActivationTokenModel, token_id) is None


class TestActivateUser:
    async def test_sets_is_active_true(self, db_session: AsyncSession, user: User):
        assert user.is_active is False

        await activate_user(user)
        await db_session.commit()

        assert user.is_active is True
