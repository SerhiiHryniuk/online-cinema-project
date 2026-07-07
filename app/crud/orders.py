from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orders import Order, OrderItem, OrderStatus
from app.models.movies import Movie
from app.models.carts import Cart, CartItem


async def get_user_cart_with_items(db: AsyncSession, user_id: int) -> Cart | None:
    """Get user's cart with all items and movie details."""
    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.items).selectinload(CartItem.movie)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_purchased_movies(db: AsyncSession, user_id: int) -> list[int]:
    """Get list of movie IDs already purchased by the user."""
    stmt = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            and_(
                Order.user_id == user_id,
                Order.status.in_([OrderStatus.PAID, OrderStatus.PENDING])
            )
        )
        .distinct()
    )
    result = await db.execute(stmt)
    return result.scalars().all()  # type: ignore


async def get_user_pending_orders_with_movies(db: AsyncSession, user_id: int) -> list[tuple]:
    """Get user's pending orders with their movie IDs for duplicate checking."""
    stmt = (
        select(Order)
        .where(
            and_(
                Order.user_id == user_id,
                Order.status == OrderStatus.PENDING
            )
        )
        .distinct()
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    pending_with_movies = []
    for order in orders:
        items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
        items_result = await db.execute(items_stmt)
        items = items_result.scalars().all()
        movie_ids = [item.movie_id for item in items]
        pending_with_movies.append((order, movie_ids))

    return pending_with_movies


async def check_movies_available(db: AsyncSession, movie_ids: list[int]) -> tuple[list[int], list[int]]:
    """
    Check which movies are available.
    Returns tuple of (available_ids, unavailable_ids)
    """
    stmt = select(Movie.id).where(Movie.id.in_(movie_ids))
    result = await db.execute(stmt)
    available_ids = set(result.scalars().all())
    unavailable_ids = [m_id for m_id in movie_ids if m_id not in available_ids]
    return list(available_ids), unavailable_ids


async def create_order_from_cart(
    db: AsyncSession,
    user_id: int,
) -> Order:
    """Create an order from user's cart."""
    order = Order(user_id=user_id, status=OrderStatus.PENDING)
    db.add(order)
    await db.flush()
    return order


async def add_order_items(
    db: AsyncSession,
    order: Order,
    cart_items: list[CartItem],
) -> Order:
    """Add items to an order and calculate total amount."""
    total = Decimal("0.00")

    for cart_item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            movie_id=cart_item.movie_id,
            price_at_order=cart_item.movie.price,
        )
        db.add(order_item)
        total += cart_item.movie.price

    order.total_amount = total
    await db.flush()
    return order


async def clear_user_cart(db: AsyncSession, user_id: int) -> None:
    """Clear user's cart after successful order creation."""
    stmt = select(Cart).where(Cart.user_id == user_id)
    result = await db.execute(stmt)
    cart = result.scalars().first()

    if cart:
        stmt = select(CartItem).where(CartItem.cart_id == cart.id)  # type: ignore
        result = await db.execute(stmt)
        cart_items = result.scalars().all()

        for item in cart_items:
            await db.delete(item)


async def get_order_by_id(db: AsyncSession, order_id: int) -> Order | None:
    """Get order by ID with all details."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.movie)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_orders(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    per_page: int = 10,
) -> tuple[list[Order], int]:
    """Get paginated list of user's orders."""
    # Count total orders
    count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Get orders with pagination
    offset = (page - 1) * per_page
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    return orders, total  # type: ignore


async def get_all_orders(
    db: AsyncSession,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    per_page: int = 10,
) -> tuple[list[Order], int]:
    """Get filtered orders for admin."""
    conditions = []

    if user_id is not None:
        conditions.append(Order.user_id == user_id)

    if status is not None:
        conditions.append(Order.status == status)

    if start_date is not None:
        conditions.append(Order.created_at >= start_date)

    if end_date is not None:
        conditions.append(Order.created_at <= end_date)

    where_clause = and_(*conditions) if conditions else None

    # Count total
    count_stmt = select(func.count(Order.id))
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Get orders with pagination
    offset = (page - 1) * per_page
    stmt = select(Order).order_by(Order.created_at.desc()).offset(offset).limit(per_page)

    if where_clause is not None:
        stmt = stmt.where(where_clause)

    result = await db.execute(stmt)
    orders = result.scalars().all()

    return orders, total  # type: ignore


async def update_order_status(
    db: AsyncSession,
    order: Order,
    new_status: OrderStatus,
) -> Order:
    """Update order status."""
    order.status = new_status
    await db.flush()
    return order


async def can_cancel_order(order: Order) -> bool:
    """Check if order can be canceled."""
    return order.status in [OrderStatus.PENDING]


async def revalidate_order_total(db: AsyncSession, order: Order) -> Decimal:
    """
    Revalidate order total amount in case prices have changed.
    Returns the new total amount.
    """
    stmt = (
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .options(selectinload(OrderItem.movie))
    )
    result = await db.execute(stmt)
    order_items = result.scalars().all()

    new_total = Decimal("0.00")
    for item in order_items:
        new_total += item.movie.price

    return new_total
