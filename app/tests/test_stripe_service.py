import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import stripe
from app.payments_services.stripe_service import (
    create_checkout_session,
    retrieve_session,
    construct_webhook_event,
)


@pytest.mark.asyncio
async def test_create_checkout_session_success():
    order_id = 101
    user_id = 5
    items_data = [
        {"name": "Movie Ticket", "price": "12.50", "quantity": 2}
    ]
    success_url = "https://example.com/success"
    cancel_url = "https://example.com/cancel"

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"

    with patch("stripe.checkout.Session.create_async", new=AsyncMock(return_value=mock_session)) as mock_create:
        result = await create_checkout_session(
            order_id=order_id,
            user_id=user_id,
            items_data=items_data,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        assert result == mock_session
        mock_create.assert_awaited_once()
        _, kwargs = mock_create.call_args
        assert kwargs["mode"] == "payment"
        assert kwargs["success_url"] == success_url
        assert kwargs["cancel_url"] == cancel_url
        assert kwargs["metadata"] == {"order_id": "101", "user_id": "5"}
        assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 1250
        assert kwargs["line_items"][0]["quantity"] == 2
        assert "idempotency_key" in kwargs
        assert "checkout-order-101-5-" in kwargs["idempotency_key"]


@pytest.mark.asyncio
async def test_retrieve_session_success():
    session_id = "cs_test_abc"
    mock_session = MagicMock(id=session_id)

    with patch("stripe.checkout.Session.retrieve_async", new=AsyncMock(return_value=mock_session)) as mock_retrieve:
        result = await retrieve_session(session_id)

        assert result == mock_session
        mock_retrieve.assert_awaited_once_with(session_id)


@pytest.mark.asyncio
async def test_retrieve_session_stripe_error():
    session_id = "cs_test_invalid"

    with patch("stripe.checkout.Session.retrieve_async", new=AsyncMock(side_effect=stripe.error.StripeError("API Error"))):
        result = await retrieve_session(session_id)

        assert result is None


def test_construct_webhook_event_success():
    payload = b'{"type": "checkout.session.completed"}'
    sig_header = "t=123,v1=signature"
    endpoint_secret = "whsec_test_secret"
    mock_event = MagicMock(type="checkout.session.completed")

    with patch("stripe.Webhook.construct_event", return_value=mock_event) as mock_construct:
        result = construct_webhook_event(payload, sig_header, endpoint_secret)

        assert result == mock_event
        mock_construct.assert_called_once_with(payload, sig_header, endpoint_secret)
