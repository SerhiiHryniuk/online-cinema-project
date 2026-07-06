from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import CartNotFound, MovieNotFound
from app.models.carts import Cart, CartItem
from app.models.movies import Movie
from app.models.orders import Order, OrderItem, OrderStatus


async def get_or_create_cart(
    db: AsyncSession,
    user_id: int,
) -> Cart:
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.movie)
            .selectinload(Movie.genres)
        )
    )
    cart = await db.scalar(stmt)

    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart, ("items",))

    return cart


async def get_user_cart(
    db: AsyncSession,
    user_id: int,
) -> Cart:
    return await get_or_create_cart(db, user_id)


async def add_movie_to_cart(
    db: AsyncSession,
    cart_id: int,
    movie_id: int,
) -> CartItem:
    movie = await db.get(Movie, movie_id)
    if not movie:
        raise MovieNotFound

    stmt = select(CartItem).where(
        CartItem.cart_id == cart_id,
        CartItem.movie_id == movie_id,
    )
    cart_item = await db.scalar(stmt)

    if cart_item:
        return cart_item

    cart_item = CartItem(cart_id=cart_id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item, ("movie",))

    return cart_item


async def remove_movie_from_cart(
    db: AsyncSession,
    cart_id: int,
    movie_id: int,
) -> None:
    stmt = select(CartItem).where(
        CartItem.cart_id == cart_id,
        CartItem.movie_id == movie_id,
    )
    cart_item = await db.scalar(stmt)
    if not cart_item:
        raise MovieNotFound

    await db.delete(cart_item)
    await db.commit()


async def clear_cart(
    db: AsyncSession,
    cart_id: int,
) -> None:
    stmt = select(CartItem).where(CartItem.cart_id == cart_id)
    result = await db.scalars(stmt)
    items = list(result.all())

    for item in items:
        await db.delete(item)
    await db.commit()


async def is_movie_purchased(
    db: AsyncSession,
    user_id: int,
    movie_id: int,
) -> bool:
    stmt = (
        select(OrderItem)
        .join(Order)
        .where(
            Order.user_id == user_id,
            Order.status == OrderStatus.PAID,
            OrderItem.movie_id == movie_id,
        )
    )
    order_item = await db.scalar(stmt)

    return order_item is not None


async def checkout_cart(
    db: AsyncSession,
    user_id: int,
) -> Order:
    cart = await get_or_create_cart(db, user_id)
    if not cart.items:
        raise CartNotFound

    order = Order(
        user_id=user_id,
        status=OrderStatus.PAID,
        total_amount=Decimal("0.00"),
    )
    db.add(order)
    await db.flush()

    total = Decimal("0.00")
    for item in cart.items:
        movie_price = getattr(item.movie, "price", Decimal("0.00"))

        order_item = OrderItem(
            order_id=order.id,
            movie_id=item.movie_id,
            price_at_order=movie_price,
        )
        db.add(order_item)
        total += movie_price

    order.total_amount = total

    for item in cart.items:
        await db.delete(item)

    await db.commit()
    await db.refresh(order, ("items",))

    return order


async def admin_get_user_cart(
    db: AsyncSession,
    user_id: int,
) -> Cart:
    return await get_or_create_cart(db, user_id)


async def check_movie_in_any_cart(
    db: AsyncSession,
    movie_id: int,
) -> bool:
    stmt = select(CartItem).where(CartItem.movie_id == movie_id).limit(1)
    cart_item = await db.scalar(stmt)

    return cart_item is not None
