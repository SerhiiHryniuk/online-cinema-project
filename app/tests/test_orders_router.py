import pytest
import pytest_asyncio
from decimal import Decimal
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.routers.orders import router as orders_router
from app.security.tokens import create_access_token
from app.security import hash_password
from app.models.orders import Order, OrderStatus, OrderItem
from app.models.carts import Cart, CartItem
from app.models.movies import Movie, Certification
from app.models.accounts import User, UserGroup, UserGroupEnum


@pytest_asyncio.fixture
async def admin_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.ADMIN)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def user_group(db_session: AsyncSession) -> UserGroup:
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()
    return group


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, admin_group: UserGroup) -> User:
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        group_id=admin_group.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession, user_group: UserGroup) -> User:
    user = User(
        email="user@example.com",
        hashed_password=hash_password("user123"),
        group_id=user_group.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def user_token(regular_user: User) -> str:
    return create_access_token(str(regular_user.id))


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(str(admin_user.id))


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = FastAPI()
    app.include_router(orders_router, prefix="/api/v1/orders")

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_order_success(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    cert = Certification(name="PG")
    db_session.add(cert)
    await db_session.commit()

    movies = [
        Movie(
            name=f"Movie {i}",
            year=2020 + i,
            time=120,
            imdb=8.0,
            votes=100000,
            description=f"Description {i}",
            price=Decimal(f"{10 + i}.99"),
            certification_id=cert.id,
        )
        for i in range(2)
    ]
    db_session.add_all(movies)
    await db_session.commit()

    cart = Cart(user_id=regular_user.id)
    db_session.add(cart)
    await db_session.commit()

    for movie in movies:
        cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)
    await db_session.commit()

    response = await client.post(
        "/api/v1/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == OrderStatus.PENDING
    assert data["total_amount"] is not None


@pytest.mark.asyncio
async def test_create_order_empty_cart(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    cart = Cart(user_id=regular_user.id)
    db_session.add(cart)
    await db_session.commit()

    response = await client.post(
        "/api/v1/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 400
    assert "Cart is empty" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_user_orders(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    for i in range(2):
        order = Order(user_id=regular_user.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
        db_session.add(order)
    await db_session.commit()

    response = await client.get(
        "/api/v1/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_user_orders_pagination(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    for i in range(15):
        order = Order(user_id=regular_user.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
        db_session.add(order)
    await db_session.commit()

    response = await client.get(
        "/api/v1/orders/?page=1&per_page=10",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert len(data["items"]) == 10
    assert data["total_pages"] == 2


@pytest.mark.asyncio
async def test_get_order_details(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    cert = Certification(name="PG")
    db_session.add(cert)
    await db_session.commit()

    movie = Movie(
        name="Test Movie",
        year=2020,
        time=120,
        imdb=8.0,
        votes=100000,
        description="Test",
        price=Decimal("10.00"),
        certification_id=cert.id,
    )
    db_session.add(movie)
    await db_session.commit()

    order = Order(user_id=regular_user.id, status=OrderStatus.PENDING, total_amount=Decimal("10.00"))
    db_session.add(order)
    await db_session.commit()

    order_item = OrderItem(
        order_id=order.id,
        movie_id=movie.id,
        price_at_order=Decimal("10.00"),
    )
    db_session.add(order_item)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/orders/{order.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order.id
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_order_details_not_found(client: httpx.AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/orders/999",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_order_pending(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    order = Order(user_id=regular_user.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
    db_session.add(order)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/orders/{order.id}/cancel",
        json={"reason": "Changed my mind"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == OrderStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_order_paid_fails(client: httpx.AsyncClient, db_session: AsyncSession, regular_user: User, user_token: str):
    order = Order(user_id=regular_user.id, status=OrderStatus.PAID, total_amount=Decimal("20.00"))
    db_session.add(order)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/orders/{order.id}/cancel",
        json={"reason": "Changed my mind"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 400
    assert "cannot be canceled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_order_not_found(client: httpx.AsyncClient, user_token: str):
    response = await client.post(
        "/api/v1/orders/999/cancel",
        json={"reason": "Changed my mind"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_admin_orders_requires_admin(client: httpx.AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/orders/admin/all",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_admin_orders_success(client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User, admin_token: str, user_group: UserGroup):
    user1 = User(email="user1@example.com", hashed_password="hashed", group_id=user_group.id)
    user2 = User(email="user2@example.com", hashed_password="hashed", group_id=user_group.id)
    db_session.add_all([user1, user2])
    await db_session.commit()

    order1 = Order(user_id=user1.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
    order2 = Order(user_id=user2.id, status=OrderStatus.PAID, total_amount=Decimal("30.00"))
    db_session.add_all([order1, order2])
    await db_session.commit()

    response = await client.get(
        "/api/v1/orders/admin/all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_admin_orders_filter_by_status(client: httpx.AsyncClient, db_session: AsyncSession, admin_token: str, user_group: UserGroup):
    user = User(email="user@example.com", hashed_password="hashed", group_id=user_group.id)
    db_session.add(user)
    await db_session.commit()

    order_pending = Order(user_id=user.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
    order_paid = Order(user_id=user.id, status=OrderStatus.PAID, total_amount=Decimal("20.00"))
    db_session.add_all([order_pending, order_paid])
    await db_session.commit()

    response = await client.get(
        "/api/v1/orders/admin/all?status=paid",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == OrderStatus.PAID


@pytest.mark.asyncio
async def test_list_admin_orders_filter_by_user(client: httpx.AsyncClient, db_session: AsyncSession, admin_token: str, user_group: UserGroup):
    user1 = User(email="user1@example.com", hashed_password="hashed", group_id=user_group.id)
    user2 = User(email="user2@example.com", hashed_password="hashed", group_id=user_group.id)
    db_session.add_all([user1, user2])
    await db_session.commit()

    order1 = Order(user_id=user1.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
    order2 = Order(user_id=user2.id, status=OrderStatus.PENDING, total_amount=Decimal("20.00"))
    db_session.add_all([order1, order2])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/orders/admin/all?user_id={user1.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
