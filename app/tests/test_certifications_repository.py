from app.repositories.certifications import CertificationRepository


async def test_create_certification(db_session):
    repo = CertificationRepository(db_session)
    cert = await repo.create("R")
    await db_session.commit()

    assert cert.id is not None
    assert cert.name == "R"


async def test_get_certification_by_name(db_session):
    repo = CertificationRepository(db_session)
    await repo.create("PG-13")
    await db_session.commit()

    found = await repo.get_by_name("PG-13")

    assert found is not None
    assert found.name == "PG-13"


async def test_update_certification(db_session):
    repo = CertificationRepository(db_session)
    cert = await repo.create("PG")
    await db_session.commit()

    updated = await repo.update(cert, "PG-13")
    await db_session.commit()

    assert updated.id == cert.id
    assert updated.name == "PG-13"


async def test_delete_certification(db_session):
    repo = CertificationRepository(db_session)
    cert = await repo.create("NC-17")
    await db_session.commit()
    cert_id = cert.id

    await repo.delete(cert)
    await db_session.commit()

    found = await repo.get_by_id(cert_id)
    assert found is None


async def test_get_all_certifications_sorted(db_session):
    repo = CertificationRepository(db_session)
    await repo.create("R")
    await repo.create("G")
    await db_session.commit()

    certs = await repo.get_all()

    names = [c.name for c in certs]
    assert names == sorted(names)


async def test_get_certification_by_id_missing(db_session):
    repo = CertificationRepository(db_session)

    found = await repo.get_by_id(999)

    assert found is None
