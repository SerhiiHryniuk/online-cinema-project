from app.crud.directors import (
    create_director,
    delete_director,
    get_all_directors,
    get_director_by_id,
    get_director_by_name,
    update_director,
)


async def test_create_director(db_session):
    director = await create_director(db_session, "Christopher Nolan")
    await db_session.commit()

    assert director.id is not None
    assert director.name == "Christopher Nolan"


async def test_get_director_by_name(db_session):
    await create_director(db_session, "Bong Joon-ho")
    await db_session.commit()

    found = await get_director_by_name(db_session, "Bong Joon-ho")

    assert found is not None
    assert found.name == "Bong Joon-ho"


async def test_update_director(db_session):
    director = await create_director(db_session, "Nolan")
    await db_session.commit()

    updated = await update_director(
        db_session, director, "Christopher Nolan"
    )
    await db_session.commit()

    assert updated.id == director.id
    assert updated.name == "Christopher Nolan"


async def test_delete_director(db_session):
    director = await create_director(db_session, "Extra")
    await db_session.commit()
    director_id = director.id

    await delete_director(db_session, director)
    await db_session.commit()

    found = await get_director_by_id(db_session, director_id)
    assert found is None


async def test_get_all_directors_sorted(db_session):
    await create_director(db_session, "Zack")
    await create_director(db_session, "Alfred")
    await db_session.commit()

    directors = await get_all_directors(db_session)

    names = [d.name for d in directors]
    assert names == sorted(names)
