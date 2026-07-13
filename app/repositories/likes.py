from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interactions import Like, LikeType
from app.repositories.base import BaseRepository


class LikeRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_user_like(self, user_id: int, movie_id: int) -> Like | None:
        stmt = select(Like).where(
            Like.user_id == user_id,
            Like.movie_id == movie_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_like(
        self,
        user_id: int,
        movie_id: int,
        like_type: LikeType,
    ) -> Like:
        like = await self.get_user_like(user_id, movie_id)

        if like is None:
            like = Like(
                user_id=user_id,
                movie_id=movie_id,
                type=like_type,
            )
            self.db.add(like)
        else:
            like.type = like_type

        await self.db.flush()
        return like

    async def remove_like(self, user_id: int, movie_id: int) -> bool:
        like = await self.get_user_like(user_id, movie_id)
        if like is None:
            return False

        await self.db.delete(like)
        await self.db.flush()
        return True

    async def count_movie_likes(self, movie_id: int) -> tuple[int, int]:
        stmt = (
            select(Like.type, func.count())
            .where(Like.movie_id == movie_id)
            .group_by(Like.type)
        )
        result = await self.db.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}

        likes = counts.get(LikeType.LIKE, 0)
        dislikes = counts.get(LikeType.DISLIKE, 0)
        return likes, dislikes
