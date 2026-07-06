import pytest
from decimal import Decimal

from app.crud import orders as orders_crud
from app.models.orders import Order, OrderStatus, OrderItem
from app.models.carts import Cart, CartItem
from app.models.movies import Movie, Certification
from app.models.accounts import User, UserGroup, UserGroupEnum


async def setup_test_data(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="test_order@example.com",
        hashed_password="hashed",
        group_id=group.id,
    )
    cert = Certification(name="PG-13")
    db_session.add_all([user, cert])
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
        for i in range(5)
    ]
    db_session.add_all(movies)
    await db_session.commit()

    cart = Cart(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    return user, movies, cart


@pytest.mark.asyncio
async def test_get_user_cart_with_items(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    result = await orders_crud.get_user_cart_with_items(db_session, user.id)

    assert result is not None
    assert result.id == cart.id
    assert len(result.items) == 1
    assert result.items[0].movie_id == movies[0].id


@pytest.mark.asyncio
async def test_get_user_cart_with_items_empty_cart(db_session):
    user, _, _ = await setup_test_data(db_session)

    result = await orders_crud.get_user_cart_with_items(db_session, user.id)

    assert result is not None
    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_check_movies_available(db_session):
    user, movies, _ = await setup_test_data(db_session)

    available, unavailable = await orders_crud.check_movies_available(
        db_session, [movies[0].id, movies[1].id, 999]
    )

    assert len(available) == 2
    assert len(unavailable) == 1
    assert 999 in unavailable


@pytest.mark.asyncio
async def test_create_order_from_cart(db_session):
    user, _, _ = await setup_test_data(db_session)

    order = await orders_crud.create_order_from_cart(db_session, user.id)
    await db_session.commit()

    assert order.id is not None
    assert order.user_id == user.id
    assert order.status == OrderStatus.PENDING
    assert order.total_amount is None


@pytest.mark.asyncio
async def test_add_order_items(db_session):
    user, movies, cart = await setup_test_data(db_session)

    for movie in movies[:3]:
        cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    await db_session.commit()

    expected_total = sum(m.price for m in movies[:3])

    assert order.total_amount == expected_total
    assert len(order.items) == 3


@pytest.mark.asyncio
async def test_clear_user_cart(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    await orders_crud.clear_user_cart(db_session, user.id)
    await db_session.commit()

    result = await orders_crud.get_user_cart_with_items(db_session, user.id)
    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_get_order_by_id(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    await db_session.commit()

    result = await orders_crud.get_order_by_id(db_session, order.id)

    assert result is not None
    assert result.id == order.id
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_get_user_orders(db_session):
    user, movies, cart = await setup_test_data(db_session)

    for i in range(3):
        cart_items = [CartItem(cart_id=cart.id, movie_id=movies[i].id)]
        db_session.add_all(cart_items)
        await db_session.commit()

        cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
        order = await orders_crud.create_order_from_cart(db_session, user.id)
        await orders_crud.add_order_items(db_session, order, cart_full.items)
        await orders_crud.clear_user_cart(db_session, user.id)
        await db_session.commit()

    orders, total = await orders_crud.get_user_orders(db_session, user.id, page=1, per_page=10)

    assert len(orders) == 3
    assert total == 3


@pytest.mark.asyncio
async def test_get_user_orders_pagination(db_session):
    user, movies, cart = await setup_test_data(db_session)

    for i in range(15):
        cart_items = [CartItem(cart_id=cart.id, movie_id=movies[i % 5].id)]
        db_session.add_all(cart_items)
        await db_session.commit()

        cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
        order = await orders_crud.create_order_from_cart(db_session, user.id)
        await orders_crud.add_order_items(db_session, order, cart_full.items)
        await orders_crud.clear_user_cart(db_session, user.id)
        await db_session.commit()

    orders_page1, total = await orders_crud.get_user_orders(db_session, user.id, page=1, per_page=10)
    orders_page2, _ = await orders_crud.get_user_orders(db_session, user.id, page=2, per_page=10)

    assert len(orders_page1) == 10
    assert len(orders_page2) == 5
    assert total == 15


@pytest.mark.asyncio
async def test_get_user_purchased_movies(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    order.status = OrderStatus.PAID
    await db_session.commit()

    purchased = await orders_crud.get_user_purchased_movies(db_session, user.id)

    assert len(purchased) == 1
    assert movies[0].id in purchased


@pytest.mark.asyncio
async def test_update_order_status(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    await db_session.commit()

    assert order.status == OrderStatus.PENDING

    order = await orders_crud.update_order_status(db_session, order, OrderStatus.PAID)
    await db_session.commit()

    assert order.status == OrderStatus.PAID


@pytest.mark.asyncio
async def test_can_cancel_order_pending(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    await orders_crud.add_order_items(db_session, order, cart_full.items)
    await db_session.commit()

    result = await orders_crud.can_cancel_order(order)
    assert result is True


@pytest.mark.asyncio
async def test_can_cancel_order_paid(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    order.status = OrderStatus.PAID
    await db_session.commit()

    result = await orders_crud.can_cancel_order(order)
    assert result is False


@pytest.mark.asyncio
async def test_revalidate_order_total(db_session):
    user, movies, cart = await setup_test_data(db_session)

    cart_item = CartItem(cart_id=cart.id, movie_id=movies[0].id)
    db_session.add(cart_item)
    await db_session.commit()

    cart_full = await orders_crud.get_user_cart_with_items(db_session, user.id)
    order = await orders_crud.create_order_from_cart(db_session, user.id)
    order = await orders_crud.add_order_items(db_session, order, cart_full.items)
    await db_session.commit()

    original_total = order.total_amount
    new_total = await orders_crud.revalidate_order_total(db_session, order)

    assert new_total == original_total


@pytest.mark.asyncio
async def test_get_all_orders(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user1 = User(email="user1@example.com", hashed_password="hashed", group_id=group.id)
    user2 = User(email="user2@example.com", hashed_password="hashed", group_id=group.id)
    db_session.add_all([user1, user2])
    await db_session.commit()

    cert = Certification(name="PG")
    movie = Movie(
        name="Test",
        year=2020,
        time=120,
        imdb=8.0,
        votes=100000,
        description="Test",
        price=Decimal("10.00"),
        certification_id=cert.id,
    )
    db_session.add_all([cert, movie])
    await db_session.commit()

    for user in [user1, user2]:
        cart = Cart(user_id=user.id)
        db_session.add(cart)
        await db_session.commit()

        cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)
        await db_session.commit()

        order = Order(user_id=user.id, status=OrderStatus.PENDING)
        db_session.add(order)
        await db_session.commit()

    orders, total = await orders_crud.get_all_orders(db_session)

    assert total == 2
    assert len(orders) == 2


@pytest.mark.asyncio
async def test_get_all_orders_filter_by_user(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user1 = User(email="user1@example.com", hashed_password="hashed", group_id=group.id)
    user2 = User(email="user2@example.com", hashed_password="hashed", group_id=group.id)
    db_session.add_all([user1, user2])
    await db_session.commit()

    order1 = Order(user_id=user1.id, status=OrderStatus.PENDING)
    order2 = Order(user_id=user2.id, status=OrderStatus.PENDING)
    db_session.add_all([order1, order2])
    await db_session.commit()

    orders, total = await orders_crud.get_all_orders(db_session, user_id=user1.id)

    assert total == 1
    assert len(orders) == 1
    assert orders[0].user_id == user1.id


@pytest.mark.asyncio
async def test_get_all_orders_filter_by_status(db_session):
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(email="user@example.com", hashed_password="hashed", group_id=group.id)
    db_session.add(user)
    await db_session.commit()

    order_pending = Order(user_id=user.id, status=OrderStatus.PENDING)
    order_paid = Order(user_id=user.id, status=OrderStatus.PAID)
    db_session.add_all([order_pending, order_paid])
    await db_session.commit()

    orders, total = await orders_crud.get_all_orders(db_session, status=OrderStatus.PAID)

    assert total == 1
    assert len(orders) == 1
    assert orders[0].status == OrderStatus.PAID
