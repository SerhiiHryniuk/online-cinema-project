from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interactions import (
    Comment,
    Notification,
    NotificationType,
)


async def get_comment_by_id(
    db: AsyncSession,
    comment_id: int,
) -> Comment | None:
    stmt = select(Comment).where(Comment.id == comment_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_comment(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
    content: str,
    parent_id: int | None,
) -> Comment:
    comment = Comment(
        user_id=user_id,
        movie_id=movie_id,
        content=content,
        parent_id=parent_id,
    )
    db.add(comment)
    await db.flush()

    if parent_id is not None:
        parent = await get_comment_by_id(db, parent_id)
        if parent is not None and parent.user_id != user_id:
            notification = Notification(
                user_id=parent.user_id,
                comment_id=comment.id,
                type=NotificationType.COMMENT_REPLY,
                message="Someone replied to your comment.",
            )
            db.add(notification)
            await db.flush()

    return comment


async def get_movie_comments(
    db: AsyncSession,
    movie_id: int,
) -> list[Comment]:
    stmt = (
        select(Comment)
        .where(
            Comment.movie_id == movie_id,
            Comment.parent_id.is_(None),
        )
        .options(selectinload(Comment.replies))
        .order_by(Comment.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
