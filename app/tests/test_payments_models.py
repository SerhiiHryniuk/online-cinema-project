from decimal import Decimal
from sqlalchemy import select
from app.models import (
    User,
    UserGroup,
    UserGroupEnum,
    Movie,
    Certification,
    Order,
    OrderItem,
    Payment,
    PaymentItem,
    PaymentStatus
)


class TestPaymentModels:
    async def _setup_data(self, db_session):
        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.flush()

        user = User(
            email="payment_test@example.com",
            hashed_password="hashed",
            group_id=group.id,
        )
        db_session.add(user)

        cert = Certification(name="PG-13")
        db_session.add(cert)
        await db_session.flush()

        movie = Movie(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=2000000,
            description="A thief who steals corporate secrets...",
            price=Decimal("19.99"),
            certification_id=cert.id
        )
        db_session.add(movie)
        await db_session.flush()

        order = Order(
            user_id=user.id,
            total_amount=Decimal("19.99")
        )
        db_session.add(order)
        await db_session.flush()

        order_item = OrderItem(
            order_id=order.id,
            movie_id=movie.id,
            price_at_order=movie.price
        )
        db_session.add(order_item)
        await db_session.flush()

        return user, order, order_item

    async def test_create_payment_with_default_status(self, db_session):
        setup_result = await self._setup_data(db_session)
        user = setup_result[0]
        order = setup_result[1]

        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=Decimal("19.99"),
            external_payment_id="ch_stripe_12345"
        )
        db_session.add(payment)
        await db_session.commit()

        assert payment.id is not None
        assert str(payment.status) == str(PaymentStatus.PENDING)
        assert payment.user_id == user.id
        assert payment.order_id == order.id
        assert payment.amount == Decimal("19.99")
        assert payment.external_payment_id == "ch_stripe_12345"
        assert payment.created_at is not None

    async def test_payment_item_relationship(self, db_session):
        user, order, order_item = await self._setup_data(db_session)

        payment = Payment(
            user_id=user.id,
            order_id=order.id,
            amount=Decimal("19.99"),
            status=PaymentStatus.SUCCESSFUL
        )
        db_session.add(payment)
        await db_session.flush()

        payment_item = PaymentItem(
            payment_id=payment.id,
            order_item_id=order_item.id,
            price_at_payment=Decimal("19.99")
        )
        db_session.add(payment_item)
        await db_session.commit()

        result = await db_session.execute(
            select(Payment).where(Payment.id == payment.id)
        )
        db_payment = result.scalar_one()
        await db_session.refresh(db_payment, ["items"])

        assert len(db_payment.items) == 1
        assert db_payment.items[0].order_item_id == order_item.id
        assert db_payment.items[0].price_at_payment == Decimal("19.99")

    async def test_cascade_delete_payment(self, db_session):
        user, order, order_item = await self._setup_data(db_session)

        payment = Payment(user_id=user.id, order_id=order.id, amount=Decimal("19.99"))
        db_session.add(payment)
        await db_session.flush()

        payment_item = PaymentItem(
            payment_id=payment.id,
            order_item_id=order_item.id,
            price_at_payment=Decimal("19.99")
        )
        db_session.add(payment_item)
        await db_session.commit()
        await db_session.delete(payment)
        await db_session.commit()

        result = await db_session.execute(
            select(PaymentItem).where(PaymentItem.id == payment_item.id)
        )
        assert result.scalar_one_or_none() is None
