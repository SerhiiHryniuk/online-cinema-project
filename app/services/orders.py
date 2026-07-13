from app.exceptions import (
    AllMoviesPurchasedError,
    DuplicatePendingOrderError,
    EmptyCartError,
    NoAvailableMoviesError,
)
from app.models.interactions import NotificationType
from app.models.orders import Order
from app.repositories.notifications import NotificationRepository
from app.repositories.orders import OrderRepository


class OrderService:
    def __init__(
        self,
        orders: OrderRepository,
        notifications: NotificationRepository,
    ) -> None:
        self.orders = orders
        self.notifications = notifications

    async def create_order_from_cart(self, user_id: int) -> Order:
        cart = await self.orders.get_user_cart_with_items(user_id)
        if not cart or not cart.items:
            raise EmptyCartError

        cart_item_ids = [item.movie_id for item in cart.items]
        available_ids, unavailable_ids = await self.orders.check_movies_available(
            cart_item_ids
        )

        for movie_id in unavailable_ids:
            await self.notifications.create(
                user_id=user_id,
                comment_id=None,
                type_=NotificationType.COMMENT_LIKE,
                message=f"Movie (ID: {movie_id}) is not available and excluded from your order.",
            )

        items_to_order = [item for item in cart.items if item.movie_id in available_ids]
        if not items_to_order:
            raise NoAvailableMoviesError

        purchased_ids = await self.orders.get_user_purchased_movies(user_id)
        items_to_order = [
            item for item in items_to_order if item.movie_id not in purchased_ids
        ]
        if not items_to_order:
            raise AllMoviesPurchasedError

        movie_ids_to_order = [item.movie_id for item in items_to_order]
        pending_orders = await self.orders.get_user_pending_orders_with_movies(user_id)

        for order, movie_ids in pending_orders:
            order_movie_set = set(movie_ids) if movie_ids else set()
            if order_movie_set == set(movie_ids_to_order):
                raise DuplicatePendingOrderError

        order = await self.orders.create(user_id)
        order = await self.orders.add_items(order, items_to_order)
        await self.orders.clear_user_cart(user_id)

        return order
