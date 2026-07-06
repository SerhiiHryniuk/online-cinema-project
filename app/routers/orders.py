from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, allowed_roles_user
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
from app.models.orders import Order, OrderStatus
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
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
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
        db.add(
            Notification(
                user_id=user.id,
                type=NotificationType.COMMENT_LIKE,
                message=f"Movie (ID: {movie_id}) is not available and excluded.",
            )
        )

    items_to_order = [
        item for item in cart.items if item.movie_id in available_ids
    ]

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
            detail="All movies already purchased.",
        )

    movie_ids_to_order = [item.movie_id for item in items_to_order]

    pending_orders = await orders_crud.get_user_pending_orders_with_movies(
        db, user.id
    )

    for order, movie_ids in pending_orders:
        if set(movie_ids or []) == set(movie_ids_to_order):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate pending order.",
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
    status_code=status.HTTP_200_OK,
)
async def list_user_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    orders, total = await orders_crud.get_user_orders(
        db, user.id, page, per_page
    )

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(o) for o in orders],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get(
    "/{order_id}",
    response_model=OrderDetailSchema,
    summary="Get Order Details",
)
async def get_order_details(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderDetailSchema:
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
)
async def cancel_order(
    order_id: int,
    payload: OrderCancelRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
    order = await orders_crud.get_order_by_id(db, order_id)

    if not order or order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    if not await orders_crud.can_cancel_order(order):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be canceled.",
        )

    order = await orders_crud.update_order_status(
        db, order, OrderStatus.CANCELED
    )

    await db.commit()
    await db.refresh(order)

    return OrderResponseSchema.model_validate(order)


@router.get(
    "/admin/all",
    response_model=OrderListResponseSchema,
)
async def list_all_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[
        User,
        Depends(allowed_roles_user(UserGroupEnum.ADMIN)),
    ],
    user_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    orders, total = await orders_crud.get_all_orders(
        db,
        user_id=user_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page,
    )

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(o) for o in orders],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )
