import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cart, CartItem, User, UserGroup, UserGroupEnum
from app.models.movies import Certification, Movie

if TYPE_CHECKING:
    from app.models.accounts import User as AccountUser
    from app.models.movies import Movie as MovieModel


async def _create_test_user(db_session: AsyncSession) -> "AccountUser":
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    await db_session.commit()

    user = User(
        email="cart_test@example.com",
        hashed_password="hashed_password",
        group_id=group.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _create_test_movie(db_session: AsyncSession) -> "MovieModel":
    certification = Certification(name="PG-13-CART")
    db_session.add(certification)
    await db_session.commit()

    movie = Movie(
        name="Cart Test Movie",
        year=2026,
        time=120,
        imdb=7.5,
        votes=100,
        description="Test movie for shopping cart operations.",
        price=Decimal("9.99"),
        certification_id=certification.id,
    )
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)
    return movie


async def test_create_cart_for_user(db_session: AsyncSession):
    user = await _create_test_user(db_session)

    new_cart = Cart(user_id=user.id)
    db_session.add(new_cart)
    await db_session.commit()

    result = await db_session.execute(
        select(Cart).where(Cart.user_id == user.id)
    )
    cart = result.scalar_one_or_none()

    assert cart is not None
    assert cart.user_id == user.id

    await db_session.refresh(cart, ["items"])
    assert len(cart.items) == 0


async def test_add_item_to_cart(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    movie = await _create_test_movie(db_session)

    cart = Cart(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
    db_session.add(cart_item)
    await db_session.commit()

    await db_session.refresh(cart, ["items"])

    assert len(cart.items) == 1
    assert cart.items[0].movie_id == movie.id
    assert isinstance(cart.items[0].added_at, datetime.datetime)


async def test_unique_cart_movie_constraint(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    movie = await _create_test_movie(db_session)

    cart = Cart(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    item1 = CartItem(cart_id=cart.id, movie_id=movie.id)
    db_session.add(item1)
    await db_session.commit()

    item2 = CartItem(cart_id=cart.id, movie_id=movie.id)
    db_session.add(item2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


async def test_cart_cascade_delete(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    movie = await _create_test_movie(db_session)

    cart = Cart(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    cart_item = CartItem(cart_id=cart.id, movie_id=movie.id)
    db_session.add(cart_item)
    await db_session.commit()

    await db_session.delete(cart_item)
    await db_session.delete(cart)
    await db_session.commit()

    result = await db_session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    items = result.scalars().all()

    assert len(items) == 0
