import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, Payment, PaymentItem, PaymentStatus, OrderStatus
from app.payments_services import payment_db
from app.tasks.emails import send_payment_success_email_task

logger = logging.getLogger(__name__)


async def process_webhook_event(db: AsyncSession, event: Any) -> dict:
    if not isinstance(event, dict):
        event = event.to_dict()

    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})
    if not isinstance(event_data, dict):
        event_data = event_data.to_dict()

    if event_type == "checkout.session.completed":
        return await _handle_checkout_completed(db, event_data)
    elif event_type == "payment_intent.payment_failed":
        return await _handle_payment_failed(db, event_data)
    elif event_type == "checkout.session.expired":
        return await _handle_checkout_expired(db, event_data)
    elif event_type == "charge.refunded":
        return await _handle_charge_refunded(db, event_data)

    return {"status": "unhandled_event_type"}


async def _handle_checkout_completed(db: AsyncSession, session: Any) -> dict:
    session_id = session.get("id")
    intent_id = session.get("payment_intent")
    metadata = session.get("metadata", {})

    try:
        order_id = int(metadata.get("order_id", 0))
        user_id = int(metadata.get("user_id", 0))
    except (ValueError, TypeError):
        logger.error(f"Webhook metadata parsing failed for session {session_id}")
        await db.rollback()
        return {"status": "invalid_metadata"}

    stripe_amount_cents = int(session.get("amount_total", 0))

    stmt_payment = select(Payment).filter(
        Payment.session_id == session_id
    ).with_for_update()
    res_payment = await db.execute(stmt_payment)
    payment = res_payment.unique().scalar_one_or_none()

    if not payment:
        logger.error(f"Payment not found for completed session {session_id}, order {order_id}")
        return {"status": "payment_not_found"}

    stmt_order = (
        select(Order)
        .filter(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
        .with_for_update()
    )
    res_order = await db.execute(stmt_order)
    order = res_order.unique().scalar_one_or_none()

    if not order or order.user_id != user_id:
        await db.rollback()
        return {"status": "order_not_found_or_access_denied"}

    if order.total_amount is None:
        logger.error(f"Order {order_id} has no total_amount set, cannot verify payment")
        await db.rollback()
        return {"status": "order_amount_not_set"}

    order_amount_cents = int(
        (Decimal(str(order.total_amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )

    if order_amount_cents != stripe_amount_cents:
        logger.critical(
            f"SECURITY ALERT: Amount mismatch for order {order_id}. "
            f"Expected cents: {order_amount_cents}, Stripe cents: {stripe_amount_cents}"
        )
        await db.rollback()
        return {"status": "amount_mismatch_validation_failed"}

    if payment.status == PaymentStatus.SUCCESSFUL:
        await db.rollback()
        return {"status": "payment_already_processed"}

    await payment_db.update_status(
        db,
        payment.id,
        PaymentStatus.SUCCESSFUL,
        external_payment_id=intent_id,
        session_id=session_id
    )

    stmt_items = select(PaymentItem).filter(PaymentItem.payment_id == payment.id)
    existing_items = (await db.execute(stmt_items)).scalars().all()

    if not existing_items:
        for item in order.items:
            payment_item = PaymentItem(
                payment_id=payment.id,
                order_item_id=item.id,
                price_at_payment=item.price_at_order
            )
            db.add(payment_item)

    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.PAID
    else:
        logger.critical(
            f"CRITICAL RACE CONDITION / OUT-OF-ORDER: Payment for order {order_id} marked SUCCESSFUL "
            f"but order status was already '{order.status}'!"
        )

    await db.commit()

    send_payment_success_email_task.delay(order.user.email, order.id, str(order.total_amount))

    return {"status": "success"}


async def _handle_payment_failed(db: AsyncSession, payment_intent: Any) -> dict:
    intent_id = payment_intent.get("id")

    stmt_payment = select(Payment).filter(
        Payment.external_payment_id == intent_id
    ).with_for_update()
    res_payment = await db.execute(stmt_payment)
    payment = res_payment.unique().scalar_one_or_none()

    if not payment:
        return {"status": "payment_not_found"}

    if payment.status != PaymentStatus.PENDING:
        await db.rollback()
        return {"status": "ignored_state"}

    await payment_db.update_status(db, payment.id, PaymentStatus.FAILED)

    await db.commit()
    return {"status": "payment_failed_handled"}


async def _handle_checkout_expired(db: AsyncSession, session: Any) -> dict:
    session_id = session.get("id")

    stmt_payment = select(Payment).filter(Payment.session_id == session_id).with_for_update()
    res_payment = await db.execute(stmt_payment)
    payment = res_payment.unique().scalar_one_or_none()

    if not payment:
        return {"status": "payment_not_found"}

    if payment.status != PaymentStatus.PENDING:
        await db.rollback()
        return {"status": "ignored_state"}

    await payment_db.update_status(db, payment.id, PaymentStatus.CANCELED)

    stmt_order = select(Order).filter(Order.id == payment.order_id).with_for_update()
    order = (await db.execute(stmt_order)).unique().scalar_one_or_none()

    if order and order.status == OrderStatus.PENDING:
        order.status = OrderStatus.CANCELED

    await db.commit()
    return {"status": "session_expired_handled"}


async def _handle_charge_refunded(db: AsyncSession, charge: Any) -> dict:
    intent_id = charge.get("payment_intent")
    is_fully_refunded = charge.get("refunded", False)

    if not is_fully_refunded:
        return {"status": "partial_refund_ignored"}

    stmt_payment = select(Payment).filter(
        Payment.external_payment_id == intent_id
    ).with_for_update()
    res_payment = await db.execute(stmt_payment)
    payment = res_payment.unique().scalar_one_or_none()

    if not payment:
        return {"status": "payment_not_found"}

    if payment.status != PaymentStatus.SUCCESSFUL:
        await db.rollback()
        return {"status": "ignored_state"}

    await payment_db.update_status(db, payment.id, PaymentStatus.REFUNDED)

    stmt_order = select(Order).filter(Order.id == payment.order_id).with_for_update()
    order = (await db.execute(stmt_order)).unique().scalar_one_or_none()

    if order and order.status == OrderStatus.PAID:
        order.status = OrderStatus.CANCELED

    await db.commit()
    return {"status": "refund_handled"}
