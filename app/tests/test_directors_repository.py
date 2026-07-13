from app.repositories.directors import DirectorRepository


async def test_create_director(db_session):
    repo = DirectorRepository(db_session)
    director = await repo.create("Christopher Nolan")
    await db_session.commit()

    assert director.id is not None
    assert director.name == "Christopher Nolan"


async def test_get_director_by_name(db_session):
    repo = DirectorRepository(db_session)
    await repo.create("Bong Joon-ho")
    await db_session.commit()

    found = await repo.get_by_name("Bong Joon-ho")

    assert found is not None
    assert found.name == "Bong Joon-ho"


async def test_update_director(db_session):
    repo = DirectorRepository(db_session)
    director = await repo.create("Nolan")
    await db_session.commit()

    updated = await repo.update(director, "Christopher Nolan")
    await db_session.commit()

    assert updated.id == director.id
    assert updated.name == "Christopher Nolan"


async def test_delete_director(db_session):
    repo = DirectorRepository(db_session)
    director = await repo.create("Extra")
    await db_session.commit()
    director_id = director.id

    await repo.delete(director)
    await db_session.commit()

    found = await repo.get_by_id(director_id)
    assert found is None


async def test_get_all_directors_sorted(db_session):
    repo = DirectorRepository(db_session)
    await repo.create("Zack")
    await repo.create("Alfred")
    await db_session.commit()

    all_directors = await repo.get_all()

    names = [d.name for d in all_directors]
    assert names == sorted(names)


async def test_get_director_by_id_missing(db_session):
    repo = DirectorRepository(db_session)

    found = await repo.get_by_id(999)

    assert found is None
