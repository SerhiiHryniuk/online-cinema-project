from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    allowed_roles_user,
    get_current_user,
    get_order_repo,
    get_order_service,
)
from app.db.session import get_db
from app.exceptions import (
    AllMoviesPurchasedError,
    DuplicatePendingOrderError,
    EmptyCartError,
    NoAvailableMoviesError,
)
from app.models.accounts import User, UserGroupEnum
from app.models.orders import OrderStatus
from app.repositories.orders import OrderRepository
from app.schemas.orders import (
    OrderCancelRequestSchema,
    OrderDetailSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
)
from app.services.orders import OrderService

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
    order_service: Annotated[OrderService, Depends(get_order_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
    try:
        order = await order_service.create_order_from_cart(user.id)
    except EmptyCartError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty.")
    except NoAvailableMoviesError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No available movies in cart.")
    except AllMoviesPurchasedError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All movies in cart are already purchased.")
    except DuplicatePendingOrderError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A pending order with the same movies already exists.")

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
    orders: Annotated[OrderRepository, Depends(get_order_repo)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    items, total = await orders.get_user_orders(user.id, page, per_page)
    total_pages = (total + per_page - 1) // per_page

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(order) for order in items],
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
    responses={404: {"description": "Not Found - Order not found or not owned by user."}},
)
async def get_order_details(
    order_id: int,
    orders: Annotated[OrderRepository, Depends(get_order_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderDetailSchema:
    order = await orders.get_by_id(order_id)

    if not order or order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

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
    orders: Annotated[OrderRepository, Depends(get_order_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderResponseSchema:
    order = await orders.get_by_id(order_id)

    if not order or order.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    can_cancel = await orders.can_cancel(order)
    if not can_cancel:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order cannot be canceled at this stage.")

    order = await orders.update_status(order, OrderStatus.CANCELED)
    await db.commit()
    await db.refresh(order)

    return OrderResponseSchema.model_validate(order)


@router.get(
    "/admin/all",
    response_model=OrderListResponseSchema,
    summary="List All Orders (Admin)",
    description="Get all orders with optional filters. Requires admin role.",
    status_code=status.HTTP_200_OK,
    responses={403: {"description": "Forbidden - Requires admin role."}},
)
async def list_all_orders(
    admin_user: Annotated[User, Depends(allowed_roles_user(UserGroupEnum.ADMIN))],
    orders: Annotated[OrderRepository, Depends(get_order_repo)],
    user_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
) -> OrderListResponseSchema:
    items, total = await orders.get_all(
        user_id=user_id, status=status_filter, start_date=start_date,
        end_date=end_date, page=page, per_page=per_page,
    )
    total_pages = (total + per_page - 1) // per_page

    return OrderListResponseSchema(
        items=[OrderResponseSchema.model_validate(order) for order in items],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
    )
