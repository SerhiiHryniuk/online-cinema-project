from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.accounts import User
from app.models.tokens import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)
from app.repositories.base import BaseRepository


class ActivationTokenRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def create(self, user_id: int) -> ActivationTokenModel:
        token = ActivationTokenModel(user_id=user_id)
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_with_user(
        self, email: str, token: str
    ) -> ActivationTokenModel | None:
        stmt = (
            select(ActivationTokenModel)
            .options(joinedload(ActivationTokenModel.user))
            .join(User)
            .where(
                User.email == email,
                ActivationTokenModel.token == token,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_id(self, user_id: int) -> ActivationTokenModel | None:
        stmt = select(ActivationTokenModel).where(
            ActivationTokenModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete(self, token: ActivationTokenModel) -> None:
        await self.db.delete(token)


class RefreshTokenRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_token(self, token: str) -> RefreshTokenModel | None:
        stmt = select(RefreshTokenModel).filter_by(token=token)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_id(self, user_id: int) -> RefreshTokenModel | None:
        stmt = select(RefreshTokenModel).filter_by(user_id=user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete(self, token: RefreshTokenModel) -> None:
        await self.db.delete(token)


class PasswordResetTokenRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def create(self, user_id: int) -> PasswordResetTokenModel:
        token = PasswordResetTokenModel(user_id=user_id)
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_by_user_id(self, user_id: int) -> PasswordResetTokenModel | None:
        stmt = select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_with_user_by_token(
        self, token: str
    ) -> PasswordResetTokenModel | None:
        stmt = (
            select(PasswordResetTokenModel)
            .options(joinedload(PasswordResetTokenModel.user))
            .where(PasswordResetTokenModel.token == token)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete(self, token: PasswordResetTokenModel) -> None:
        await self.db.delete(token)
