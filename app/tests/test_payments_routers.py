from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import (
    Certification,
    Movie,
    Order,
    OrderItem,
    Payment,
    PaymentStatus,
    User,
    UserGroup,
    UserGroupEnum,
)
from app.routers.payments import router as payments_router
from app.security.tokens import create_access_token

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="buyer@example.com",
        hashed_password="hashed",
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def order_with_item(db_session: AsyncSession, user: User) -> Order:
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
        certification_id=cert.id,
    )
    db_session.add(movie)
    await db_session.flush()

    order = Order(user_id=user.id, total_amount=Decimal("19.99"))
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(order_id=order.id, movie_id=movie.id, price_at_order=Decimal("19.99"))
    db_session.add(item)
    await db_session.commit()

    return order


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    u = User(
        email="other_buyer@example.com",
        hashed_password="hashed",
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def moderator(db_session: AsyncSession) -> User:
    group = UserGroup(name=UserGroupEnum.MODERATOR)
    db_session.add(group)
    await db_session.flush()

    u = User(
        email="moderator@example.com",
        hashed_password="hashed",
        group_id=group.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def payments_from_two_users(
    db_session: AsyncSession, user: User, order_with_item: Order, other_user: User
) -> tuple[Payment, Payment]:
    payment_1 = Payment(
        user_id=user.id,
        order_id=order_with_item.id,
        amount=Decimal("19.99"),
        status=PaymentStatus.SUCCESSFUL,
    )
    db_session.add(payment_1)

    cert = Certification(name="R")
    db_session.add(cert)
    await db_session.flush()

    movie = Movie(
        name="Other Movie",
        year=2015,
        time=120,
        imdb=7.0,
        votes=1000,
        description="test",
        price=Decimal("9.99"),
        certification_id=cert.id,
    )
    db_session.add(movie)
    await db_session.flush()

    other_order = Order(user_id=other_user.id, total_amount=Decimal("9.99"))
    db_session.add(other_order)
    await db_session.flush()

    item = OrderItem(order_id=other_order.id, movie_id=movie.id, price_at_order=Decimal("9.99"))
    db_session.add(item)

    payment_2 = Payment(
        user_id=other_user.id,
        order_id=other_order.id,
        amount=Decimal("9.99"),
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment_2)
    await db_session.commit()

    return payment_1, payment_2


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = FastAPI()
    app.include_router(payments_router)

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestCreateCheckout:
    async def test_create_checkout_route_success(self, client: httpx.AsyncClient, user: User, order_with_item: Order):
        token = create_access_token(user_id=user.id)
        mock_session = MagicMock(id="cs_test_123", url="https://stripe.com/pay/test", payment_intent="pi_123")

        with patch(
            "app.payments_services.stripe_service.create_checkout_session",
            new=AsyncMock(return_value=mock_session),
        ) as mock_create:
            response = await client.post(
                "/checkout/",
                json={"order_id": order_with_item.id},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://stripe.com/pay/test"
        assert data["session_id"] == "cs_test_123"
        mock_create.assert_awaited_once()

    async def test_create_checkout_route_unauthorized(self, client: httpx.AsyncClient, order_with_item: Order):
        response = await client.post("/checkout/", json={"order_id": order_with_item.id})
        assert response.status_code in (401, 403)

    async def test_create_checkout_route_empty_order(self, client: httpx.AsyncClient, db_session: AsyncSession, user: User):
        order = Order(user_id=user.id)
        db_session.add(order)
        await db_session.commit()

        token = create_access_token(user_id=user.id)
        response = await client.post(
            "/checkout/",
            json={"order_id": order.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    async def test_create_checkout_route_not_found(self, client: httpx.AsyncClient, user: User):
        token = create_access_token(user_id=user.id)
        response = await client.post(
            "/checkout/",
            json={"order_id": 999999},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestAdminPayments:
    async def test_admin_endpoint_forbidden_for_regular_user(
        self, client: httpx.AsyncClient, user: User, payments_from_two_users: tuple[Payment, Payment]
    ):
        token = create_access_token(user_id=user.id)
        response = await client.get("/admin/", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_admin_endpoint_unauthorized(self, client: httpx.AsyncClient):
        response = await client.get("/admin/")
        assert response.status_code in (401, 403)

    async def test_admin_endpoint_lists_all_users_payments(
        self, client: httpx.AsyncClient, moderator: User, payments_from_two_users: tuple[Payment, Payment]
    ):
        token = create_access_token(user_id=moderator.id)
        response = await client.get("/admin/", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_admin_endpoint_filters_by_user_id(
        self, client: httpx.AsyncClient, moderator: User, user: User, payments_from_two_users: tuple[Payment, Payment]
    ):
        token = create_access_token(user_id=moderator.id)
        response = await client.get(
            f"/admin/?user_id={user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["order_id"] == payments_from_two_users[0].order_id

    async def test_admin_endpoint_filters_by_status(
        self, client: httpx.AsyncClient, moderator: User, payments_from_two_users: tuple[Payment, Payment]
    ):
        token = create_access_token(user_id=moderator.id)
        response = await client.get(
            "/admin/?status=pending",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"
