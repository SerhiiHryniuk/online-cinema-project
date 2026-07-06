from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app import crud
from app.db.session import get_db
from app.api.deps import get_current_user, allowed_roles_user
from app.models import User
from app.schemas.carts import CartReadSchema
from app.exceptions import CartNotFound, MovieNotFound

router = APIRouter()


@router.get("/me", response_model=CartReadSchema)
async def get_my_cart(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
):
    return await crud.get_user_cart(db, current_user.id)


@router.post("/me/items/{movie_id}", response_model=CartReadSchema)
async def add_item_to_cart(
        movie_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
):
    is_purchased = await crud.is_movie_purchased(db, current_user.id, movie_id)
    if is_purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Repeat purchases are not allowed. "
                "You already own this movie."
            ),
        )

    cart = await crud.get_or_create_cart(db, current_user.id)

    if any(item.movie_id == movie_id for item in cart.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie is already in your cart.",
        )

    try:
        await crud.add_movie_to_cart(db, cart.id, movie_id)

        return await crud.get_user_cart(db, current_user.id)
    except MovieNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.delete("/me/items/{movie_id}", response_model=CartReadSchema)
async def remove_item_from_cart(
        movie_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
):
    cart = await crud.get_or_create_cart(db, current_user.id)
    try:
        await crud.remove_movie_from_cart(db, cart.id, movie_id)

        return await crud.get_user_cart(db, current_user.id)
    except MovieNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.delete("/me/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_cart(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
):
    cart = await crud.get_or_create_cart(db, current_user.id)
    await crud.clear_cart(db, cart.id)


@router.post("/me/checkout")
async def checkout_my_cart(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        order = await crud.checkout_cart(db, current_user.id)

        return {"message": "Payment successful", "order_id": order.id}
    except CartNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.get(
    "/user/{user_id}",
    response_model=CartReadSchema,
    dependencies=[Depends(allowed_roles_user("admin", "moderator"))],
)
async def admin_get_user_cart(
        user_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
):
    return await crud.admin_get_user_cart(db, user_id)
