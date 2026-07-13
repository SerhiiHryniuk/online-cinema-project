from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactions import Notification, NotificationType
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, notification_id: int) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))

        stmt = stmt.order_by(Notification.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        comment_id: int | None,
        type_: NotificationType,
        message: str,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            comment_id=comment_id,
            type=type_,
            message=message,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def mark_read(self, notification: Notification) -> None:
        notification.is_read = True
        await self.db.flush()
