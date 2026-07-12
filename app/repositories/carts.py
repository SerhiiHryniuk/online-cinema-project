from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import MovieNotFound
from app.models.carts import Cart, CartItem
from app.models.movies import Movie
from app.models.orders import Order, OrderItem, OrderStatus
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_or_create(self, user_id: int) -> Cart:
        stmt = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.movie)
                .selectinload(Movie.genres)
            )
        )
        cart = await self.db.scalar(stmt)

        if not cart:
            cart = Cart(user_id=user_id)
            self.db.add(cart)
            await self.db.commit()
            await self.db.refresh(cart, ("items",))

        return cart

    async def add_movie(self, cart_id: int, movie_id: int) -> CartItem:
        movie = await self.db.get(Movie, movie_id)
        if not movie:
            raise MovieNotFound

        stmt = (
            select(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.movie_id == movie_id)
            .options(selectinload(CartItem.movie))
        )
        cart_item = await self.db.scalar(stmt)
        if cart_item:
            return cart_item

        cart_item = CartItem(cart_id=cart_id, movie_id=movie_id)
        self.db.add(cart_item)
        await self.db.commit()

        stmt = select(CartItem).options(selectinload(CartItem.movie)).where(CartItem.id == cart_item.id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def remove_movie(self, cart_id: int, movie_id: int) -> None:
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id, CartItem.movie_id == movie_id
        )
        cart_item = await self.db.scalar(stmt)
        if not cart_item:
            raise MovieNotFound

        await self.db.delete(cart_item)
        await self.db.commit()

    async def clear(self, cart_id: int) -> None:
        stmt = select(CartItem).where(CartItem.cart_id == cart_id)
        result = await self.db.scalars(stmt)
        items = list(result.all())

        for item in items:
            await self.db.delete(item)
        await self.db.commit()

    async def is_movie_purchased(self, user_id: int, movie_id: int) -> bool:
        stmt = (
            select(OrderItem)
            .join(Order)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.PAID,
                OrderItem.movie_id == movie_id,
            )
        )
        order_item = await self.db.scalar(stmt)
        return order_item is not None

    async def check_movie_in_any_cart(self, movie_id: int) -> bool:
        stmt = select(CartItem).where(CartItem.movie_id == movie_id).limit(1)
        cart_item = await self.db.scalar(stmt)
        return cart_item is not None
