import asyncio

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from sqlalchemy import select

from app.models import User, UserGroup, UserGroupEnum
from app.security import hash_password


async def seed_admin() -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(User).join(UserGroup).where(UserGroup.name == UserGroupEnum.ADMIN)
        result = await db.execute(stmt)
        if result.scalars().first():
            print("Admin already exists.")
            return

        group_stmt = select(UserGroup).where(UserGroup.name == UserGroupEnum.ADMIN)
        group_res = await db.execute(group_stmt)
        admin_group = group_res.scalars().first()

        admin = User(
            email=settings.SUPERUSER_EMAIL,
            hashed_password=hash_password(settings.SUPERUSER_PASSWORD),
            group_id=admin_group.id,  # type: ignore[union-attr]
            is_active=True
        )
        db.add(admin)
        await db.commit()

if __name__ == "__main__":
    asyncio.run(seed_admin())
