import hashlib
import json
import stripe
from typing import List, Dict, Any, Optional


from stripe.params.checkout import (
    SessionCreateParamsLineItem,
    SessionCreateParamsLineItemPriceData,
    SessionCreateParamsLineItemPriceDataProductData,
)

from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(
    order_id: int,
    user_id: int,
    items_data: List[Dict[str, Any]],
    success_url: str,
    cancel_url: str,
    currency: str = "usd",
    attempt: int = 0,
) -> stripe.checkout.Session:
    payload_string = json.dumps(items_data, sort_keys=True)
    payload_hash = hashlib.sha256(payload_string.encode("utf-8")).hexdigest()[:16]
    idempotency_key = f"checkout-order-{order_id}-{user_id}-{payload_hash}-{attempt}"

    line_items: List[SessionCreateParamsLineItem] = []
    for item in items_data:
        quantity = int(item.get("quantity", 1))
        product_data: SessionCreateParamsLineItemPriceDataProductData = {
            "name": item["name"],
        }
        price_data: SessionCreateParamsLineItemPriceData = {
            "currency": currency,
            "unit_amount": int(round(float(item["price"]) * 100)),
            "product_data": product_data,
        }
        line_items.append({
            "price_data": price_data,
            "quantity": quantity,
        })

    session = await stripe.checkout.Session.create_async(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "order_id": str(order_id),
            "user_id": str(user_id)
        },
        idempotency_key=idempotency_key
    )
    return session


async def retrieve_session(session_id: str) -> Optional[stripe.checkout.Session]:
    try:
        return await stripe.checkout.Session.retrieve_async(session_id)
    except stripe.error.StripeError:
        return None


def construct_webhook_event(payload: bytes, sig_header: str, endpoint_secret: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
