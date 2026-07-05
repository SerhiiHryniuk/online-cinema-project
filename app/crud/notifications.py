from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactions import Notification


async def get_user_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool,
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.user_id == user_id
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))

    stmt = stmt.order_by(Notification.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_notification_by_id(
    db: AsyncSession,
    notification_id: int,
) -> Notification | None:
    stmt = select(Notification).where(
        Notification.id == notification_id
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def mark_notification_read(
    db: AsyncSession,
    notification: Notification,
) -> None:
    notification.is_read = True
    await db.flush()
