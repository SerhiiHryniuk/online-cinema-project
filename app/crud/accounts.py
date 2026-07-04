from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.accounts import User, UserGroup, UserGroupEnum
from app.models.tokens import ActivationTokenModel


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_group_by_name(db: AsyncSession, name: UserGroupEnum) -> UserGroup | None:
    stmt = select(UserGroup).where(UserGroup.name == name)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_user(db: AsyncSession, email: str, hashed_password: str, group_id: int) -> User:
    user = User(email=email, hashed_password=hashed_password, group_id=group_id)
    db.add(user)
    await db.flush()
    return user


async def create_activation_token(db: AsyncSession, user_id: int) -> ActivationTokenModel:
    token = ActivationTokenModel(user_id=user_id)
    db.add(token)
    await db.flush()
    return token


async def get_activation_token_with_user(
    db: AsyncSession, email: str, token: str
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
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_activation_token_by_user_id(
    db: AsyncSession, user_id: int
) -> ActivationTokenModel | None:
    stmt = select(ActivationTokenModel).where(ActivationTokenModel.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def delete_activation_token(db: AsyncSession, token: ActivationTokenModel) -> None:
    await db.delete(token)


async def activate_user(user: User) -> None:
    user.is_active = True
