from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.api.deps import (
    allowed_roles_user,
    get_cart_repo,
    get_cart_service,
    get_current_user,
)

from app.exceptions import CartNotFound, MovieNotFound
from app.models import User
from app.repositories.carts import CartRepository
from app.schemas.carts import CartReadSchema
from app.services.carts import CartService

router = APIRouter()


@router.get("/me", response_model=CartReadSchema)
async def get_my_cart(
        carts: Annotated[CartRepository, Depends(get_cart_repo)],
        current_user: Annotated[User, Depends(get_current_user)],
) -> CartReadSchema:
    cart = await carts.get_or_create(current_user.id)
    return CartReadSchema.model_validate(cart)


@router.post("/me/items/{movie_id}", response_model=CartReadSchema)
async def add_item_to_cart(
        movie_id: int,
        carts: Annotated[CartRepository, Depends(get_cart_repo)],
        current_user: Annotated[User, Depends(get_current_user)],
) -> CartReadSchema:
    is_purchased = await carts.is_movie_purchased(current_user.id, movie_id)
    if is_purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repeat purchases are not allowed. You already own this movie.",
        )

    cart = await carts.get_or_create(current_user.id)

    if any(item.movie_id == movie_id for item in cart.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie is already in your cart.",
        )

    try:
        await carts.add_movie(cart.id, movie_id)
        carts.db.expire(cart, ["items"])
        updated_cart = await carts.get_or_create(current_user.id)
        return CartReadSchema.model_validate(updated_cart)
    except MovieNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.delete("/me/items/{movie_id}", response_model=CartReadSchema)
async def remove_item_from_cart(
        movie_id: int,
        carts: Annotated[CartRepository, Depends(get_cart_repo)],
        current_user: Annotated[User, Depends(get_current_user)],
) -> CartReadSchema:
    cart = await carts.get_or_create(current_user.id)
    try:
        await carts.remove_movie(cart.id, movie_id)
        carts.db.expire(cart, ["items"])
        updated_cart = await carts.get_or_create(current_user.id)
        return CartReadSchema.model_validate(updated_cart)
    except MovieNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.delete("/me/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_cart(
        carts: Annotated[CartRepository, Depends(get_cart_repo)],
        current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    cart = await carts.get_or_create(current_user.id)
    await carts.clear(cart.id)
    carts.db.expire(cart, ["items"])


@router.post("/me/checkout")
async def checkout_my_cart(
        cart_service: Annotated[CartService, Depends(get_cart_service)],
        current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    try:
        order = await cart_service.checkout(current_user.id)
        return {"message": "Payment successful", "order_id": order.id}
    except CartNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.get("/user/{user_id}", response_model=CartReadSchema)
async def admin_get_user_cart(
        user_id: int,
        carts: Annotated[CartRepository, Depends(get_cart_repo)],
        _: Annotated[User, Depends(allowed_roles_user("ADMIN", "MODERATOR"))],
) -> CartReadSchema:
    cart = await carts.get_or_create(user_id)
    return CartReadSchema.model_validate(cart)
