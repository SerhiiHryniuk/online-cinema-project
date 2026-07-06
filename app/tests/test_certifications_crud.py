from app.crud.certifications import (
    create_certification,
    delete_certification,
    get_all_certifications,
    get_certification_by_id,
    get_certification_by_name,
    update_certification,
)


async def test_create_certification(db_session):
    cert = await create_certification(db_session, "R")
    await db_session.commit()

    assert cert.id is not None
    assert cert.name == "R"


async def test_get_certification_by_name(db_session):
    await create_certification(db_session, "PG-13")
    await db_session.commit()

    found = await get_certification_by_name(db_session, "PG-13")

    assert found is not None
    assert found.name == "PG-13"


async def test_update_certification(db_session):
    cert = await create_certification(db_session, "PG")
    await db_session.commit()

    updated = await update_certification(db_session, cert, "PG-13")
    await db_session.commit()

    assert updated.id == cert.id
    assert updated.name == "PG-13"


async def test_delete_certification(db_session):
    cert = await create_certification(db_session, "NC-17")
    await db_session.commit()
    cert_id = cert.id

    await delete_certification(db_session, cert)
    await db_session.commit()

    found = await get_certification_by_id(db_session, cert_id)
    assert found is None


async def test_get_all_certifications_sorted(db_session):
    await create_certification(db_session, "R")
    await create_certification(db_session, "G")
    await db_session.commit()

    certs = await get_all_certifications(db_session)

    names = [c.name for c in certs]
    assert names == sorted(names)
