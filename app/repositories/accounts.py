from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.accounts import User, UserGroup, UserGroupEnum
from app.repositories.base import BaseRepository
from app.security import verify_password


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_with_group_by_id(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.group))
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(
        self, email: str, hashed_password: str, group_id: int
    ) -> User:
        user = User(
            email=email, hashed_password=hashed_password, group_id=group_id
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.get_by_email(email)
        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    async def activate(self, user: User) -> None:
        user.is_active = True

    async def update_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password


class UserGroupRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_name(self, name: UserGroupEnum) -> UserGroup | None:
        stmt = select(UserGroup).where(UserGroup.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()
