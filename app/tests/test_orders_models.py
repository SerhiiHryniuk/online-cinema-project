from decimal import Decimal
from sqlalchemy import select
from app.models import User, UserGroup, UserGroupEnum, Movie, Certification, Order, OrderItem, OrderStatus


class TestOrderModels:
    async def _setup_data(self, db_session):
        group = UserGroup(name=UserGroupEnum.USER)
        db_session.add(group)
        await db_session.flush()
        user = User(
            email="order_test@example.com",
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
        return user, movie

    async def test_create_order(self, db_session):
        user, movie = await self._setup_data(db_session)
        order = Order(
            user_id=user.id,
            status=OrderStatus.PENDING,
            total_amount=Decimal("19.99")
        )
        db_session.add(order)
        await db_session.commit()
        assert order.id is not None
        assert order.status == OrderStatus.PENDING
        assert order.user_id == user.id
        assert order.total_amount == Decimal("19.99")
        assert order.created_at is not None

    async def test_order_item_relationship(self, db_session):
        user, movie = await self._setup_data(db_session)

        order = Order(user_id=user.id)
        db_session.add(order)
        await db_session.flush()

        item = OrderItem(
            order_id=order.id,
            movie_id=movie.id,
            price_at_order=movie.price
        )
        db_session.add(item)
        await db_session.commit()

        await db_session.refresh(order, ["items"])
        await db_session.refresh(movie, ["order_items"])

        assert len(order.items) == 1
        assert order.items[0].movie_id == movie.id
        assert order.items[0].price_at_order == Decimal("19.99")

        assert len(movie.order_items) == 1
        assert movie.order_items[0].order_id == order.id

    async def test_cascade_delete_order(self, db_session):
        user, movie = await self._setup_data(db_session)
        order = Order(user_id=user.id)
        db_session.add(order)
        await db_session.flush()
        item = OrderItem(
            order_id=order.id,
            movie_id=movie.id,
            price_at_order=movie.price
        )
        db_session.add(item)
        await db_session.commit()

        await db_session.delete(order)
        await db_session.commit()

        result = await db_session.execute(select(OrderItem).where(OrderItem.id == item.id))
        assert result.scalar_one_or_none() is None

    async def test_user_orders_relationship(self, db_session):
        user, movie = await self._setup_data(db_session)

        order = Order(user_id=user.id)
        db_session.add(order)
        await db_session.commit()

        await db_session.refresh(user, ["orders"])
        assert len(user.orders) == 1
        assert user.orders[0].id == order.id

    async def test_order_default_status(self, db_session):
        user, _ = await self._setup_data(db_session)
        order = Order(user_id=user.id)
        db_session.add(order)
        await db_session.commit()
        assert order.status == OrderStatus.PENDING
