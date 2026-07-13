import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel, RefreshTokenModel
from app.repositories.accounts import UserGroupRepository, UserRepository
from app.repositories.tokens import ActivationTokenRepository, RefreshTokenRepository
from app.security import hash_password

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


@pytest.fixture
def users(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


@pytest.fixture
def user_groups(db_session: AsyncSession) -> UserGroupRepository:
    return UserGroupRepository(db_session)


@pytest.fixture
def activation_tokens(db_session: AsyncSession) -> ActivationTokenRepository:
    return ActivationTokenRepository(db_session)


@pytest.fixture
def refresh_tokens(db_session: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(db_session)


class TestGetUserByEmail:
    async def test_returns_existing_user(
        self, db_session: AsyncSession, users: UserRepository, user: User
    ):
        found = await users.get_by_email("crud@example.com")

        assert found is not None
        assert found.id == user.id

    async def test_returns_none_when_missing(self, users: UserRepository):
        assert await users.get_by_email("missing@example.com") is None


class TestGetUserGroupByName:
    async def test_returns_existing_group(
        self, user_groups: UserGroupRepository, user_group: UserGroup
    ):
        found = await user_groups.get_by_name(UserGroupEnum.USER)

        assert found is not None
        assert found.id == user_group.id

    async def test_returns_none_when_missing(self, user_groups: UserGroupRepository):
        assert await user_groups.get_by_name(UserGroupEnum.ADMIN) is None


class TestCreateUser:
    async def test_creates_user_with_expected_fields(
        self, db_session: AsyncSession, users: UserRepository, user_group: UserGroup
    ):
        created = await users.create(
            email="new-user@example.com",
            hashed_password="hashed-pw",
            group_id=user_group.id,
        )
        await db_session.commit()

        assert created.id is not None
        assert created.email == "new-user@example.com"
        assert created.hashed_password == "hashed-pw"
        assert created.is_active is False


class TestActivationTokenRepo:
    async def test_create_activation_token(
        self, db_session: AsyncSession, activation_tokens: ActivationTokenRepository, user: User
    ):
        token = await activation_tokens.create(user_id=user.id)
        await db_session.commit()

        assert token.id is not None
        assert token.user_id == user.id

    async def test_get_activation_token_with_user(
        self, db_session: AsyncSession, activation_tokens: ActivationTokenRepository, user: User
    ):
        token = await activation_tokens.create(user_id=user.id)
        await db_session.commit()

        found = await activation_tokens.get_with_user(email=user.email, token=token.token)

        assert found is not None
        assert found.id == token.id
        assert found.user.id == user.id

    async def test_get_activation_token_with_user_returns_none_for_wrong_token(
        self, db_session: AsyncSession, activation_tokens: ActivationTokenRepository, user: User
    ):
        await activation_tokens.create(user_id=user.id)
        await db_session.commit()

        found = await activation_tokens.get_with_user(email=user.email, token="wrong-token")

        assert found is None

    async def test_get_activation_token_by_user_id(
        self, db_session: AsyncSession, activation_tokens: ActivationTokenRepository, user: User
    ):
        token = await activation_tokens.create(user_id=user.id)
        await db_session.commit()

        found = await activation_tokens.get_by_user_id(user.id)

        assert found is not None
        assert found.id == token.id

    async def test_get_activation_token_by_user_id_returns_none_when_missing(
        self, activation_tokens: ActivationTokenRepository, user: User
    ):
        assert await activation_tokens.get_by_user_id(user.id) is None

    async def test_delete_activation_token(
        self, db_session: AsyncSession, activation_tokens: ActivationTokenRepository, user: User
    ):
        token = await activation_tokens.create(user_id=user.id)
        await db_session.commit()
        token_id = token.id

        await activation_tokens.delete(token)
        await db_session.commit()

        assert await db_session.get(ActivationTokenModel, token_id) is None


class TestActivateUser:
    async def test_sets_is_active_true(
        self, db_session: AsyncSession, users: UserRepository, user: User
    ):
        assert user.is_active is False

        await users.activate(user)
        await db_session.commit()

        assert user.is_active is True


class TestGetUserById:
    async def test_returns_existing_user(self, users: UserRepository, user: User):
        found = await users.get_by_id(user.id)

        assert found is not None
        assert found.id == user.id

    async def test_returns_none_when_missing(self, users: UserRepository):
        assert await users.get_by_id(999_999) is None


class TestAuthenticateUser:
    @pytest_asyncio.fixture
    async def user_with_known_password(
        self, db_session: AsyncSession, user_group: UserGroup
    ) -> User:
        u = User(
            email="auth@example.com",
            hashed_password=hash_password("CorrectPass123"),
            group_id=user_group.id,
        )
        db_session.add(u)
        await db_session.commit()
        return u

    async def test_returns_user_with_correct_credentials(
        self, users: UserRepository, user_with_known_password: User
    ):
        found = await users.authenticate(
            email="auth@example.com", password="CorrectPass123"
        )

        assert found is not None
        assert found.id == user_with_known_password.id

    async def test_returns_none_with_wrong_password(
        self, users: UserRepository, user_with_known_password: User
    ):
        found = await users.authenticate(
            email="auth@example.com", password="WrongPassword"
        )

        assert found is None

    async def test_returns_none_for_unknown_email(self, users: UserRepository):
        found = await users.authenticate(
            email="missing@example.com", password="whatever"
        )

        assert found is None


class TestRefreshTokenRepo:
    async def test_get_refresh_token_returns_matching_record(
        self, db_session: AsyncSession, refresh_tokens: RefreshTokenRepository, user: User
    ):
        token = RefreshTokenModel(user_id=user.id, token="raw-refresh-token")
        db_session.add(token)
        await db_session.commit()

        found = await refresh_tokens.get_by_token("raw-refresh-token")

        assert found is not None
        assert found.id == token.id

    async def test_get_refresh_token_returns_none_when_missing(
        self, refresh_tokens: RefreshTokenRepository
    ):
        assert await refresh_tokens.get_by_token("does-not-exist") is None

    async def test_get_refresh_token_by_user_id(
        self, db_session: AsyncSession, refresh_tokens: RefreshTokenRepository, user: User
    ):
        token = RefreshTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()

        found = await refresh_tokens.get_by_user_id(user.id)

        assert found is not None
        assert found.id == token.id

    async def test_get_refresh_token_by_user_id_returns_none_when_missing(
        self, refresh_tokens: RefreshTokenRepository, user: User
    ):
        assert await refresh_tokens.get_by_user_id(user.id) is None

    async def test_delete_refresh_token(
        self, db_session: AsyncSession, refresh_tokens: RefreshTokenRepository, user: User
    ):
        token = RefreshTokenModel(user_id=user.id)
        db_session.add(token)
        await db_session.commit()
        token_id = token.id

        await refresh_tokens.delete(token)
        await db_session.commit()

        assert await db_session.get(RefreshTokenModel, token_id) is None
