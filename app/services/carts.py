from decimal import Decimal

from app.exceptions import CartNotFound
from app.models.orders import Order, OrderItem, OrderStatus
from app.repositories.carts import CartRepository


class CartService:
    def __init__(self, carts: CartRepository) -> None:
        self.carts = carts

    async def checkout(self, user_id: int) -> Order:
        cart = await self.carts.get_or_create(user_id)
        if not cart.items:
            raise CartNotFound

        order = Order(
            user_id=user_id,
            status=OrderStatus.PAID,
            total_amount=Decimal("0.00"),
        )
        self.carts.db.add(order)
        await self.carts.db.flush()

        total = Decimal("0.00")
        for item in cart.items:
            movie_price = getattr(item.movie, "price", Decimal("0.00"))
            order_item = OrderItem(
                order_id=order.id,
                movie_id=item.movie_id,
                price_at_order=movie_price,
            )
            self.carts.db.add(order_item)
            total += movie_price

        order.total_amount = total

        for item in cart.items:
            await self.carts.db.delete(item)

        await self.carts.db.commit()
        await self.carts.db.refresh(order, ("items",))

        return order
