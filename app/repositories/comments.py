from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interactions import Comment
from app.repositories.base import BaseRepository


class CommentRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, comment_id: int) -> Comment | None:
        stmt = select(Comment).where(Comment.id == comment_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
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
        self.db.add(comment)
        await self.db.flush()
        return comment

    async def get_movie_comments(self, movie_id: int) -> list[Comment]:
        stmt = (
            select(Comment)
            .where(
                Comment.movie_id == movie_id,
                Comment.parent_id.is_(None),
            )
            .options(selectinload(Comment.replies))
            .order_by(Comment.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())
