from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, allowed_roles_user
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
from app.models.orders import OrderStatus
from app.models.interactions import Notification, NotificationType
from app.crud import orders as orders_crud
from app.schemas.orders import (
    OrderResponseSchema,
    OrderDetailSchema,
    OrderListResponseSchema,
    OrderCancelRequestSchema,
)

router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponseSchema,
    summary="Create Order from Cart",
    description="Create a new order from user's cart. Excludes unavailable movies and already purchased movies.",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad Request - Cart is empty or validation failed."},
        404: {"description": "Not Found - Cart not found."},
    },
)
async def create_order(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
    """Create an order from user's cart."""
    cart = await orders_crud.get_user_cart_with_items(db, user.id)
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty.",
        )

    cart_item_ids = [item.movie_id for item in cart.items]

    available_ids, unavailable_ids = await orders_crud.check_movies_available(
        db, cart_item_ids
    )

    for movie_id in unavailable_ids:
        notification = Notification(
            user_id=user.id,
            type=NotificationType.COMMENT_LIKE,
            message=f"Movie (ID: {movie_id}) is not available and excluded from your order.",
        )
        db.add(notification)

    items_to_order = [item for item in cart.items if item.movie_id in available_ids]

    if not items_to_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No available movies in cart.",
        )

    purchased_ids = await orders_crud.get_user_purchased_movies(db, user.id)

    items_to_order = [
        item for item in items_to_order if item.movie_id not in purchased_ids
    ]

    if not items_to_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All movies in cart are already purchased.",
        )

    movie_ids_to_order = [item.movie_id for item in items_to_order]
    pending_orders = await orders_crud.get_user_pending_orders_with_movies(db, user.id)

    for order, movie_ids in pending_orders:
        order_movie_set = set(movie_ids) if movie_ids else set()
        if order_movie_set == set(movie_ids_to_order):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A pending order with the same movies already exists.",
            )

    order = await orders_crud.create_order_from_cart(db, user.id)
    order = await orders_crud.add_order_items(db, order, items_to_order)

    await orders_crud.clear_user_cart(db, user.id)

    await db.commit()
    await db.refresh(order)

    return OrderResponseSchema.model_validate(order)


@router.get(
    "/",
    response_model=OrderListResponseSchema,
    summary="List User Orders",
    description="Get paginated list of current user's orders.",
    status_code=status.HTTP_200_OK,
)
async def list_user_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    """Get user's orders with pagination."""
    orders, total = await orders_crud.get_user_orders(db, user.id, page, per_page)

    total_pages = (total + per_page - 1) // per_page

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(order) for order in orders],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/{order_id}",
    response_model=OrderDetailSchema,
    summary="Get Order Details",
    description="Get detailed information about a specific order.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Not Found - Order not found or not owned by user."},
    },
)
async def get_order_details(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderDetailSchema:
    """Get order details."""
    order = await orders_crud.get_order_by_id(db, order_id)

    if not order or order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    return OrderDetailSchema.model_validate(order)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponseSchema,
    summary="Cancel Order",
    description="Cancel an order before payment is completed.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Bad Request - Order cannot be canceled (already paid or completed)."},
        404: {"description": "Not Found - Order not found or not owned by user."},
    },
)
async def cancel_order(
    order_id: int,
    payload: OrderCancelRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
    """Cancel an order."""
    order = await orders_crud.get_order_by_id(db, order_id)

    if not order or order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    can_cancel = await orders_crud.can_cancel_order(order)
    if not can_cancel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be canceled at this stage.",
        )

    order = await orders_crud.update_order_status(db, order, OrderStatus.CANCELED)
    await db.commit()
    await db.refresh(order)

    return OrderResponseSchema.model_validate(order)


@router.get(
    "/admin/all",
    response_model=OrderListResponseSchema,
    summary="List All Orders (Admin)",
    description="Get all orders with optional filters. Requires admin role.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Requires admin role."},
    },
)
async def list_all_orders(
    admin_user: Annotated[User, Depends(allowed_roles_user(UserGroupEnum.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    """Get all orders for admin with filters."""
    orders, total = await orders_crud.get_all_orders(
        db,
        user_id=user_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page,
    )

    total_pages = (total + per_page - 1) // per_page

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(order) for order in orders],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )
