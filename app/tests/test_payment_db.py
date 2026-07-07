import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from app.models import PaymentStatus
from app.payments_services.payment_db import (
    get_payment_by_session_id,
    create_pending_payment,
    update_status,
    get_user_payments_history,
)


@pytest.mark.asyncio
async def test_get_payment_by_session_id_found():
    db = AsyncMock()
    mock_payment = MagicMock(session_id="cs_test_123")
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_payment))

    result = await get_payment_by_session_id(db, "cs_test_123")

    assert result == mock_payment
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_payment_by_session_id_not_found():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))

    result = await get_payment_by_session_id(db, "cs_test_invalid")

    assert result is None


@pytest.mark.asyncio
async def test_create_pending_payment():
    db = AsyncMock()
    user_id = 1
    order_id = 100
    amount = Decimal("45.50")

    result = await create_pending_payment(db, user_id, order_id, amount, "cs_test_abc", "pi_test_abc")

    assert result.user_id == user_id
    assert result.order_id == order_id
    assert result.amount == amount
    assert result.status == PaymentStatus.PENDING
    assert result.session_id == "cs_test_abc"
    assert result.external_payment_id == "pi_test_abc"
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_found():
    db = AsyncMock()
    mock_payment = MagicMock(id=1, status=PaymentStatus.PENDING)
    db.get = AsyncMock(return_value=mock_payment)

    result = await update_status(db, 1, PaymentStatus.SUCCESSFUL, external_payment_id="pi_new_123")

    assert result == mock_payment
    assert mock_payment.status == PaymentStatus.SUCCESSFUL
    assert mock_payment.external_payment_id == "pi_new_123"
    db.get.assert_awaited_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_not_found():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    result = await update_status(db, 999, PaymentStatus.FAILED)

    assert result is None
    db.get.assert_awaited_once()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_user_payments_history():
    db = AsyncMock()
    mock_payments = [MagicMock(id=1), MagicMock(id=2)]
    db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: mock_payments)))

    result = await get_user_payments_history(db, user_id=5, status=PaymentStatus.SUCCESSFUL, limit=10)

    assert result == mock_payments
    db.execute.assert_awaited_once()
