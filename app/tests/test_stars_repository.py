from app.repositories.stars import StarRepository


async def test_create_star(db_session):
    repo = StarRepository(db_session)
    star = await repo.create("Keanu Reeves")
    await db_session.commit()

    assert star.id is not None
    assert star.name == "Keanu Reeves"


async def test_get_star_by_name(db_session):
    repo = StarRepository(db_session)
    await repo.create("Al Pacino")
    await db_session.commit()

    found = await repo.get_by_name("Al Pacino")

    assert found is not None
    assert found.name == "Al Pacino"


async def test_update_star(db_session):
    repo = StarRepository(db_session)
    star = await repo.create("Keanu")
    await db_session.commit()

    updated = await repo.update(star, "Keanu Reeves")
    await db_session.commit()

    assert updated.id == star.id
    assert updated.name == "Keanu Reeves"


async def test_delete_star(db_session):
    repo = StarRepository(db_session)
    star = await repo.create("Extra")
    await db_session.commit()
    star_id = star.id

    await repo.delete(star)
    await db_session.commit()

    found = await repo.get_by_id(star_id)
    assert found is None


async def test_get_all_stars_sorted(db_session):
    repo = StarRepository(db_session)
    await repo.create("Zoe")
    await repo.create("Adam")
    await db_session.commit()

    stars = await repo.get_all()

    names = [star.name for star in stars]
    assert names == sorted(names)
