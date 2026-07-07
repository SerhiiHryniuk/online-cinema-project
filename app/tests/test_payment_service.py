import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.models import PaymentStatus, OrderStatus
from app.payments_services.payment_service import process_webhook_event


def _result_mock(scalar_value):
    result = MagicMock()
    result.unique.return_value.scalar_one_or_none.return_value = scalar_value
    return result


def _scalars_result_mock(list_value):
    result = MagicMock()
    result.scalars.return_value.all.return_value = list_value
    return result


@pytest.mark.asyncio
async def test_process_webhook_event_checkout_completed():
    db = AsyncMock()

    payment = MagicMock(id=1, order_id=101, status=PaymentStatus.PENDING)
    order = MagicMock(id=101, user_id=7, status=OrderStatus.PENDING, total_amount=Decimal("100.00"), items=[])
    order.user.email = "buyer@example.com"

    db.execute = AsyncMock(side_effect=[
        _result_mock(payment),
        _result_mock(order),
        _scalars_result_mock([]),
    ])

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_intent": "pi_123",
                "amount_total": 10000,
                "metadata": {"order_id": "101", "user_id": "7"},
            }
        },
    }

    with patch("app.payments_services.payment_db.update_status", new=AsyncMock()) as mock_update, \
            patch("app.payments_services.payment_service.send_payment_success_email_task") as mock_email_task:
        result = await process_webhook_event(db, event)

    assert result == {"status": "success"}
    assert order.status == OrderStatus.PAID
    mock_update.assert_awaited_once()
    mock_email_task.delay.assert_called_once_with("buyer@example.com", 101, "100.00")


@pytest.mark.asyncio
async def test_process_webhook_event_amount_mismatch():
    db = AsyncMock()

    payment = MagicMock(id=1, order_id=101, status=PaymentStatus.PENDING)
    order = MagicMock(id=101, user_id=7, status=OrderStatus.PENDING, total_amount=Decimal("100.00"), items=[])

    db.execute = AsyncMock(side_effect=[
        _result_mock(payment),
        _result_mock(order),
    ])

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_intent": "pi_123",
                "amount_total": 500,
                "metadata": {"order_id": "101", "user_id": "7"},
            }
        },
    }

    with patch("app.payments_services.payment_db.update_status", new=AsyncMock()) as mock_update:
        result = await process_webhook_event(db, event)

    assert result == {"status": "amount_mismatch_validation_failed"}
    mock_update.assert_not_awaited()
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_process_webhook_event_session_expired():
    db = AsyncMock()

    payment = MagicMock(id=1, order_id=101, status=PaymentStatus.PENDING)
    order = MagicMock(id=101, status=OrderStatus.PENDING)

    db.execute = AsyncMock(side_effect=[
        _result_mock(payment),
        _result_mock(order),
    ])

    with patch("app.payments_services.payment_db.update_status", new=AsyncMock()) as mock_update:
        event = {
            "type": "checkout.session.expired",
            "data": {"object": {"id": "cs_test_123"}}
        }

        result = await process_webhook_event(db, event)

    assert result == {"status": "session_expired_handled"}
    assert order.status == OrderStatus.CANCELED
    mock_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_webhook_event_payment_failed():
    db = AsyncMock()

    payment = MagicMock(id=1, order_id=101, status=PaymentStatus.PENDING)
    db.execute = AsyncMock(return_value=_result_mock(payment))

    with patch("app.payments_services.payment_db.update_status", new=AsyncMock()) as mock_update:
        event = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_123"}}
        }

        result = await process_webhook_event(db, event)

    assert result == {"status": "payment_failed_handled"}
    mock_update.assert_awaited_once_with(db, payment.id, PaymentStatus.FAILED)


@pytest.mark.asyncio
async def test_process_webhook_event_unhandled_type():
    db = AsyncMock()

    event = {
        "type": "checkout.session.async_payment_failed",
        "data": {"object": {"id": "cs_test_123"}}
    }

    result = await process_webhook_event(db, event)

    assert result == {"status": "unhandled_event_type"}
