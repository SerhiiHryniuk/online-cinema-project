from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import UserProfile


async def get_profile(db: AsyncSession, user_id: int) -> UserProfile | None:
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_profile(db: AsyncSession, user_id: int) -> UserProfile:
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    await db.flush()
    return profile


async def update_profile(profile: UserProfile, **fields: Any) -> None:
    for field, value in fields.items():
        setattr(profile, field, value)
