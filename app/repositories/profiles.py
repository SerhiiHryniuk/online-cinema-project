from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import UserProfile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_user_id(self, user_id: int) -> UserProfile | None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, user_id: int) -> UserProfile:
        profile = UserProfile(user_id=user_id)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def update(self, profile: UserProfile, **fields: Any) -> None:
        for field, value in fields.items():
            setattr(profile, field, value)
