import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profiles import ProfileRepository
from app.models.accounts import GenderEnum, User, UserGroup, UserGroupEnum

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(email="profile-crud@example.com", hashed_password="hashed", group_id=user_group.id)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
def profiles(db_session: AsyncSession) -> ProfileRepository:
    return ProfileRepository(db_session)


class TestGetProfile:
    async def test_returns_none_when_missing(self, profiles: ProfileRepository, user: User):
        assert await profiles.get_by_user_id(user.id) is None

    async def test_returns_existing_profile(
        self, db_session: AsyncSession, profiles: ProfileRepository, user: User
    ):
        created = await profiles.create(user.id)
        await db_session.commit()

        found = await profiles.get_by_user_id(user.id)

        assert found is not None
        assert found.id == created.id
        assert found.user_id == user.id


class TestCreateProfile:
    async def test_creates_empty_profile(self, profiles: ProfileRepository, user: User):
        profile = await profiles.create(user.id)

        assert profile.user_id == user.id
        assert profile.first_name is None
        assert profile.avatar is None


class TestUpdateProfile:
    async def test_updates_given_fields(
        self, db_session: AsyncSession, profiles: ProfileRepository, user: User
    ):
        profile = await profiles.create(user.id)
        await db_session.commit()

        await profiles.update(
            profile,
            first_name="Taras",
            last_name="Shevchenko",
            gender=GenderEnum.MAN,
            info="Hello there",
        )

        assert profile.first_name == "Taras"
        assert profile.last_name == "Shevchenko"
        assert profile.gender == GenderEnum.MAN
        assert profile.info == "Hello there"

    async def test_updates_avatar_field(
        self, db_session: AsyncSession, profiles: ProfileRepository, user: User
    ):
        profile = await profiles.create(user.id)
        await db_session.commit()

        await profiles.update(profile, avatar="avatars/1/new.jpg")

        assert profile.avatar == "avatars/1/new.jpg"

    async def test_leaves_unspecified_fields_untouched(
        self, db_session: AsyncSession, profiles: ProfileRepository, user: User
    ):
        profile = await profiles.create(user.id)
        await profiles.update(profile, first_name="Taras")
        await db_session.commit()

        await profiles.update(profile, last_name="Shevchenko")

        assert profile.first_name == "Taras"
        assert profile.last_name == "Shevchenko"
