import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, Payment, PaymentItem, PaymentStatus, OrderStatus
from app.payments_services import payment_db
from app.tasks.emails import send_payment_success_email_task

logger = logging.getLogger(__name__)


class StripeWebhookService:
    _EVENT_HANDLERS: dict[str, str] = {
        "checkout.session.completed": "_handle_checkout_completed",
        "payment_intent.payment_failed": "_handle_payment_failed",
        "checkout.session.expired": "_handle_checkout_expired",
        "charge.refunded": "_handle_charge_refunded",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_event(self, event: Any) -> dict:
        if not isinstance(event, dict):
            event = event.to_dict()

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})
        if not isinstance(event_data, dict):
            event_data = event_data.to_dict()

        handler_name = self._EVENT_HANDLERS.get(event_type)
        if handler_name is None:
            return {"status": "unhandled_event_type"}

        return await getattr(self, handler_name)(event_data)

    async def _guard_status(self, payment: Payment, expected: PaymentStatus) -> Optional[dict]:
        if payment.status != expected:
            await self.db.rollback()
            return {"status": "ignored_state"}
        return None

    def _transition_order(
            self,
            order: Optional[Order],
            expected_status: OrderStatus,
            new_status: OrderStatus,
    ) -> None:
        if order and order.status == expected_status:
            order.status = new_status

    async def _handle_checkout_completed(self, session: Any) -> dict:
        session_id = session.get("id")
        intent_id = session.get("payment_intent")
        metadata = session.get("metadata", {})

        try:
            order_id = int(metadata.get("order_id", 0))
            user_id = int(metadata.get("user_id", 0))
        except (ValueError, TypeError):
            logger.error(f"Webhook metadata parsing failed for session {session_id}")
            await self.db.rollback()
            return {"status": "invalid_metadata"}

        stripe_amount_cents = int(session.get("amount_total", 0))

        payment = await payment_db.get_payment_by_session_id_locked(self.db, session_id)

        if not payment:
            logger.error(f"Payment not found for completed session {session_id}, order {order_id}")
            return {"status": "payment_not_found"}

        order = await payment_db.get_order_locked_with_relations(self.db, order_id)

        if not order or order.user_id != user_id:
            await self.db.rollback()
            return {"status": "order_not_found_or_access_denied"}

        if order.total_amount is None:
            logger.error(f"Order {order_id} has no total_amount set, cannot verify payment")
            await self.db.rollback()
            return {"status": "order_amount_not_set"}

        order_amount_cents = int(
            (Decimal(str(order.total_amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

        if order_amount_cents != stripe_amount_cents:
            logger.critical(
                f"SECURITY ALERT: Amount mismatch for order {order_id}. "
                f"Expected cents: {order_amount_cents}, Stripe cents: {stripe_amount_cents}"
            )
            await self.db.rollback()
            return {"status": "amount_mismatch_validation_failed"}

        if payment.status == PaymentStatus.SUCCESSFUL:
            await self.db.rollback()
            return {"status": "payment_already_processed"}

        await payment_db.update_status(
            self.db,
            payment.id,
            PaymentStatus.SUCCESSFUL,
            external_payment_id=intent_id,
            session_id=session_id
        )

        existing_items = await payment_db.get_payment_items(self.db, payment.id)

        if not existing_items:
            for item in order.items:
                payment_item = PaymentItem(
                    payment_id=payment.id,
                    order_item_id=item.id,
                    price_at_payment=item.price_at_order
                )
                self.db.add(payment_item)

        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.PAID
        else:
            logger.critical(
                f"CRITICAL RACE CONDITION / OUT-OF-ORDER: Payment for order {order_id} marked SUCCESSFUL "
                f"but order status was already '{order.status}'!"
            )

        await self.db.commit()

        send_payment_success_email_task.delay(order.user.email, order.id, str(order.total_amount))

        return {"status": "success"}

    async def _handle_payment_failed(self, payment_intent: Any) -> dict:
        intent_id = payment_intent.get("id")

        payment = await payment_db.get_payment_by_external_id_locked(self.db, intent_id)

        if not payment:
            return {"status": "payment_not_found"}

        guard_result = await self._guard_status(payment, PaymentStatus.PENDING)
        if guard_result:
            return guard_result

        await payment_db.update_status(self.db, payment.id, PaymentStatus.FAILED)

        await self.db.commit()
        return {"status": "payment_failed_handled"}

    async def _handle_checkout_expired(self, session: Any) -> dict:
        session_id = session.get("id")

        payment = await payment_db.get_payment_by_session_id_locked(self.db, session_id)

        if not payment:
            return {"status": "payment_not_found"}

        guard_result = await self._guard_status(payment, PaymentStatus.PENDING)
        if guard_result:
            return guard_result

        await payment_db.update_status(self.db, payment.id, PaymentStatus.CANCELED)

        order = await payment_db.get_order_locked(self.db, payment.order_id)
        self._transition_order(order, OrderStatus.PENDING, OrderStatus.CANCELED)

        await self.db.commit()
        return {"status": "session_expired_handled"}

    async def _handle_charge_refunded(self, charge: Any) -> dict:
        intent_id = charge.get("payment_intent")
        is_fully_refunded = charge.get("refunded", False)

        if not is_fully_refunded:
            return {"status": "partial_refund_ignored"}

        payment = await payment_db.get_payment_by_external_id_locked(self.db, intent_id)

        if not payment:
            return {"status": "payment_not_found"}

        guard_result = await self._guard_status(payment, PaymentStatus.SUCCESSFUL)
        if guard_result:
            return guard_result

        await payment_db.update_status(self.db, payment.id, PaymentStatus.REFUNDED)

        order = await payment_db.get_order_locked(self.db, payment.order_id)
        self._transition_order(order, OrderStatus.PAID, OrderStatus.CANCELED)

        await self.db.commit()
        return {"status": "refund_handled"}


async def process_webhook_event(db: AsyncSession, event: Any) -> dict:
    return await StripeWebhookService(db).process_event(event)
