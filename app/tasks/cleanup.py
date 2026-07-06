import asyncio
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.tokens import ActivationTokenModel


async def _delete_expired_activation_tokens() -> int:
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now_utc)
        )
        await session.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]


@celery_app.task(name="app.tasks.cleanup.delete_expired_activation_tokens")
def delete_expired_activation_tokens() -> None:
    deleted_count = asyncio.run(_delete_expired_activation_tokens())
    logger.info(f"Deleted {deleted_count} expired activation token(s).")
