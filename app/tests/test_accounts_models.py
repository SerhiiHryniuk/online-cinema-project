import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import User, UserGroup, UserGroupEnum, UserProfile


async def test_create_user_group(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    result = await db_session.execute(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    )
    found = result.scalar_one()

    assert found.id is not None
    assert found.name == UserGroupEnum.USER


async def test_user_relationships(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="test@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    user.profile = UserProfile(first_name="Vlad")
    db_session.add(user)
    await db_session.commit()

    assert user.id is not None
    assert user.group.name == UserGroupEnum.USER
    assert user.profile.first_name == "Vlad"
    assert user.is_active is False


async def test_email_must_be_unique(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    first = User(
        email="same@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    db_session.add(first)
    await db_session.commit()

    duplicate = User(
        email="same@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        await db_session.commit()
