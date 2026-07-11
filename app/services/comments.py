from app.models import Comment
from app.models.interactions import NotificationType
from app.repositories.comments import CommentRepository
from app.repositories.notifications import NotificationRepository


class CommentService:
    def __init__(
        self,
        comments: CommentRepository,
        notifications: NotificationRepository,
    ) -> None:
        self.comments = comments
        self.notifications = notifications

    async def create_comment(
        self,
        user_id: int,
        movie_id: int,
        content: str,
        parent_id: int | None,
    ) -> Comment:
        comment = await self.comments.create(
            user_id, movie_id, content, parent_id
        )

        if parent_id is not None:
            parent = await self.comments.get_by_id(parent_id)
            if parent is not None and parent.user_id != user_id:
                await self.notifications.create(
                    user_id=parent.user_id,
                    comment_id=comment.id,
                    type_=NotificationType.COMMENT_REPLY,
                    message="Someone replied to your comment.",
                )

        return comment
