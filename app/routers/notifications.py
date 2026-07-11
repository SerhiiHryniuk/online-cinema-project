from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_notification_repo
from app.db.session import get_db
from app.models.accounts import User
from app.repositories.notifications import NotificationRepository
from app.schemas.comments import NotificationResponseSchema

router = APIRouter()


@router.get(
    "/",
    response_model=list[NotificationResponseSchema],
    summary="List My Notifications",
    description="Return the current user's notifications.",
    status_code=status.HTTP_200_OK,
)
async def list_notifications(
    notifications: Annotated[NotificationRepository, Depends(get_notification_repo)],
    user: Annotated[User, Depends(get_current_user)],
    unread_only: Annotated[bool, Query()] = False,
) -> list[NotificationResponseSchema]:
    items = await notifications.get_user_notifications(user.id, unread_only)
    return [
        NotificationResponseSchema.model_validate(item)
        for item in items
    ]


@router.put(
    "/{notification_id}/read/",
    response_model=NotificationResponseSchema,
    summary="Mark Notification as Read",
    description="Mark one of the current user's notifications as read.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not your notification."},
        404: {"description": "Not Found - Notification does not exist."},
    },
)
async def read_notification(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    notifications: Annotated[NotificationRepository, Depends(get_notification_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponseSchema:
    notification = await notifications.get_by_id(notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    if notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This notification does not belong to you.",
        )

    await notifications.mark_read(notification)
    await db.commit()
    await db.refresh(notification)

    return NotificationResponseSchema.model_validate(notification)
