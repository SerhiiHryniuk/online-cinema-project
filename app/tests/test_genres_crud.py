from app.crud.genres import (
    create_genre,
    delete_genre,
    get_genre_by_id,
    get_genre_by_name,
    update_genre,
)


async def test_create_genre(db_session):
    genre = await create_genre(db_session, "Sci-Fi")
    await db_session.commit()

    assert genre.id is not None
    assert genre.name == "Sci-Fi"


async def test_get_genre_by_name(db_session):
    await create_genre(db_session, "Drama")
    await db_session.commit()

    found = await get_genre_by_name(db_session, "Drama")

    assert found is not None
    assert found.name == "Drama"


async def test_update_genre(db_session):
    genre = await create_genre(db_session, "Sci-Fi")
    await db_session.commit()

    updated = await update_genre(db_session, genre, "Science Fiction")
    await db_session.commit()

    assert updated.id == genre.id
    assert updated.name == "Science Fiction"


async def test_delete_genre(db_session):
    genre = await create_genre(db_session, "Horror")
    await db_session.commit()
    genre_id = genre.id

    await delete_genre(db_session, genre)
    await db_session.commit()

    found = await get_genre_by_id(db_session, genre_id)
    assert found is None
