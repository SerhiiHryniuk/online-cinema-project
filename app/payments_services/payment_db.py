from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Payment, PaymentItem, PaymentStatus


async def get_payment_by_session_id(db: AsyncSession, session_id: str) -> Optional[Payment]:
    query = (
        select(Payment)
        .filter(Payment.session_id == session_id)
        .options(selectinload(Payment.items).selectinload(PaymentItem.order_item))
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_pending_payment(
        db: AsyncSession,
        user_id: int,
        order_id: int,
        amount: Decimal,
        session_id: Optional[str] = None,
        external_payment_id: Optional[str] = None,
) -> Payment:
    new_payment = Payment(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status=PaymentStatus.PENDING,
        session_id=session_id,
        external_payment_id=external_payment_id,
    )
    db.add(new_payment)
    await db.flush()
    return new_payment


async def update_status(
        db: AsyncSession,
        payment_id: int,
        status: PaymentStatus,
        external_payment_id: Optional[str] = None,
        session_id: Optional[str] = None,
) -> Optional[Payment]:
    payment = await db.get(Payment, payment_id)

    if payment:
        payment.status = status
        if external_payment_id:
            payment.external_payment_id = external_payment_id
        if session_id:
            payment.session_id = session_id
        await db.flush()
    return payment


async def get_user_payments_history(
        db: AsyncSession,
        user_id: Optional[int] = None,
        status: Optional[PaymentStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
) -> Sequence[Payment]:
    stmt = (
        select(Payment)
        .options(selectinload(Payment.items).selectinload(PaymentItem.order_item))
    )

    if user_id is not None:
        stmt = stmt.filter(Payment.user_id == user_id)
    if status:
        stmt = stmt.filter(Payment.status == status)
    if date_from:
        stmt = stmt.filter(Payment.created_at >= date_from)
    if date_to:
        stmt = stmt.filter(Payment.created_at <= date_to)

    stmt = stmt.order_by(Payment.created_at.desc())

    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    return res.scalars().all()
