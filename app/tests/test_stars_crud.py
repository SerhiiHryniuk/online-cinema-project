from app.crud.stars import (
    create_star,
    delete_star,
    get_all_stars,
    get_star_by_id,
    get_star_by_name,
    update_star,
)


async def test_create_star(db_session):
    star = await create_star(db_session, "Keanu Reeves")
    await db_session.commit()

    assert star.id is not None
    assert star.name == "Keanu Reeves"


async def test_get_star_by_name(db_session):
    await create_star(db_session, "Al Pacino")
    await db_session.commit()

    found = await get_star_by_name(db_session, "Al Pacino")

    assert found is not None
    assert found.name == "Al Pacino"


async def test_update_star(db_session):
    star = await create_star(db_session, "Keanu")
    await db_session.commit()

    updated = await update_star(db_session, star, "Keanu Reeves")
    await db_session.commit()

    assert updated.id == star.id
    assert updated.name == "Keanu Reeves"


async def test_delete_star(db_session):
    star = await create_star(db_session, "Extra")
    await db_session.commit()
    star_id = star.id

    await delete_star(db_session, star)
    await db_session.commit()

    found = await get_star_by_id(db_session, star_id)
    assert found is None


async def test_get_all_stars_sorted(db_session):
    await create_star(db_session, "Zoe")
    await create_star(db_session, "Adam")
    await db_session.commit()

    stars = await get_all_stars(db_session)

    names = [star.name for star in stars]
    assert names == sorted(names)
