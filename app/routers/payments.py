import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, allowed_roles_user
from app.core.config import settings
from app.db.session import get_db
from app.payments_services import stripe_service, payment_service, payment_db
from app.models import Order, User, UserGroupEnum, PaymentStatus, Payment, PaymentItem

from app.schemas.payments import (
    CheckoutRequestSchema,
    CheckoutResponseSchema,
    PaymentResponseSchema,
    PaymentItemResponseSchema,
    PaymentHistoryFilterSchema,
    AdminPaymentFilterSchema,
)

from stripe import SignatureVerificationError, StripeError

router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/payments_services/templates")


async def get_order_or_404(
        order_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> Order:
    stmt = select(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id
    ).options(selectinload(Order.items))

    res = await db.execute(stmt)
    order = res.unique().scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found or access denied"
        )
    return order


@router.get("/order/{order_id}/pay/", response_class=HTMLResponse)
async def get_payment_page(
        request: Request,
        order: Order = Depends(get_order_or_404)
):
    return templates.TemplateResponse(
        request,
        "checkout.html",
        {"order": order}
    )


@router.post("/checkout/", response_model=CheckoutResponseSchema)
async def create_checkout(
        checkout_data: CheckoutRequestSchema,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    order = await get_order_or_404(checkout_data.order_id, current_user, db)

    if not order.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot pay for an empty order"
        )

    stmt_existing = (
        select(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.id.desc())
        .with_for_update()
        .limit(1)
    )
    existing_payment = (await db.execute(stmt_existing)).scalars().first()

    if existing_payment:
        if existing_payment.status == PaymentStatus.SUCCESSFUL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order has already been paid"
            )
        if existing_payment.status == PaymentStatus.PENDING:
            stripe_session = await stripe_service.retrieve_session(existing_payment.session_id)
            if stripe_session and getattr(stripe_session, "status", None) == "open":
                return CheckoutResponseSchema(
                    checkout_url=stripe_session.url,
                    session_id=existing_payment.session_id
                )

    success_url = str(request.url_for("payment_success")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = str(request.url_for("payment_cancel")) + "?session_id={CHECKOUT_SESSION_ID}"

    items_payload = [
        {
            "name": f"Movie #{item.movie_id}",
            "price": float(item.price_at_order),
        }
        for item in order.items
    ]

    try:
        session = await stripe_service.create_checkout_session(
            order_id=order.id,
            user_id=order.user_id,
            items_data=items_payload,
            success_url=success_url,
            cancel_url=cancel_url,
            attempt=existing_payment.id if existing_payment else 0,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    except StripeError as exc:
        logger.error(f"Stripe session creation error for order {order.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment gateway communication error"
        )

    payment = await payment_db.create_pending_payment(
        db=db,
        order_id=order.id,
        user_id=order.user_id,
        amount=order.total_amount,
        session_id=session.id,
        external_payment_id=session.payment_intent
    )

    for item in order.items:
        payment_item = PaymentItem(
            payment_id=payment.id,
            order_item_id=item.id,
            price_at_payment=item.price_at_order
        )
        db.add(payment_item)

    await db.commit()

    return CheckoutResponseSchema(
        checkout_url=session.url,
        session_id=session.id
    )


@router.post("/webhook/")
async def stripe_webhook(
        request: Request,
        stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
        db: AsyncSession = Depends(get_db)
):
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header"
        )

    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        logger.critical("STRIPE_WEBHOOK_SECRET is not configured!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret is not configured"
        )

    payload = await request.body()

    try:
        event = stripe_service.construct_webhook_event(payload, stripe_signature, webhook_secret)
    except (ValueError, SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature or payload"
        )

    try:
        result = await payment_service.process_webhook_event(db, event)
    except Exception as exc:
        logger.exception(f"Webhook processing crashed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal webhook processing error"
        )

    return result


def _map_payment_to_response(payment: Payment) -> PaymentResponseSchema:
    items_mapped = [
        PaymentItemResponseSchema(
            id=item.id,
            item_id=item.order_item_id,
            price=item.price_at_payment,
        )
        for item in payment.items
    ]

    return PaymentResponseSchema(
        id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount,
        status=payment.status,
        external_payment_id=payment.external_payment_id,
        created_at=payment.created_at,
        items=items_mapped
    )


@router.get("/history/", response_model=List[PaymentResponseSchema])
async def get_payment_history(
        filters: PaymentHistoryFilterSchema = Depends(),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    payments = await payment_db.get_user_payments_history(
        db=db,
        user_id=current_user.id,
        status=filters.status,
        date_from=filters.date_from,
        date_to=filters.date_to,
        limit=filters.limit,
        offset=filters.offset
    )

    return [_map_payment_to_response(p) for p in payments]


@router.get("/admin/", response_model=List[PaymentResponseSchema])
async def get_all_payments_admin(
        filters: AdminPaymentFilterSchema = Depends(),
        _current_user: User = Depends(
            allowed_roles_user(UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR)
        ),
        db: AsyncSession = Depends(get_db)
):
    payments = await payment_db.get_user_payments_history(
        db=db,
        user_id=filters.user_id,
        status=filters.status,
        date_from=filters.date_from,
        date_to=filters.date_to,
        limit=filters.limit,
        offset=filters.offset
    )

    return [_map_payment_to_response(p) for p in payments]


@router.get("/success/", response_model=PaymentResponseSchema)
async def payment_success(
        session_id: str,
        db: AsyncSession = Depends(get_db)
):
    payment = await payment_db.get_payment_by_session_id(db, session_id)

    if not payment or payment.status == PaymentStatus.PENDING:
        stripe_session = await stripe_service.retrieve_session(session_id)
        if stripe_session and getattr(stripe_session, "payment_status", None) == "paid":
            fake_event = {
                "type": "checkout.session.completed",
                "data": {"object": stripe_session}
            }
            await payment_service.process_webhook_event(db, fake_event)
            payment = await payment_db.get_payment_by_session_id(db, session_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found"
        )

    return _map_payment_to_response(payment)


@router.get("/cancel/")
async def payment_cancel(
        session_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    if session_id:
        payment = await payment_db.get_payment_by_session_id(db, session_id)
        if payment and payment.status == PaymentStatus.PENDING:
            await payment_db.update_status(db, payment.id, PaymentStatus.CANCELED)
            await db.commit()
            return {"status": "cancelled", "message": "Payment was cancelled and marked as canceled"}

    return {"status": "cancelled", "message": "Payment generation was cancelled"}
