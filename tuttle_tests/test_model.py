"""Tests for the database model."""

import datetime
import os
import sqlite3
from pathlib import Path
from tracemalloc import stop

import pytest
from loguru import logger
from pydantic import EmailStr, ValidationError
from sqlmodel import Session, SQLModel, create_engine, select

from tuttle import model, time
from tuttle.model import (
    Address,
    Client,
    Contact,
    Contract,
    Project,
    User,
    TimeUnit,
    Cycle,
)


def store_and_retrieve(model_object):
    # in-memory sqlite db
    db_engine = create_engine("sqlite:///")
    SQLModel.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        session.add(model_object)
        session.commit()
    with Session(db_engine) as session:
        retrieved = session.exec((select(type(model_object)))).first()
    return True


def test_model_creation():
    """Test whether the entire data model can be materialized as DB tables."""
    try:
        test_home = Path("tuttle_tests/data/tmp")
        db_path = test_home / "tuttle_test.db"
        db_url = f"sqlite:///{db_path}"
        db_engine = create_engine(db_url, echo=True)
        SQLModel.metadata.create_all(db_engine)

        # test if database intact
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name;
            """
        )
        tables = cursor.fetchall()
        conn.close()
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


class TestUser:
    """Tests for the User model."""

    def test_valid_instantiation(self):
        user = User.validate(
            dict(
                name="Harry Tuttle",
                subtitle="Heating Engineer",
                email="harry@tuttle.com",
            )
        )


class TestContact:
    def test_valid_instantiation(self):
        contact = Contact.validate(
            dict(
                first_name="Sam",
                last_name="Lowry",
                email="sam.lowry@miniinf.gov",
                company="Ministry of Information",
            )
        )
        assert store_and_retrieve(contact)

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            Contact.validate(
                dict(
                    first_name="Sam",
                    last_name="Lowry",
                    email="27B-",
                    company="Ministry of Information",
                )
            )


class TestClient:
    """Tests for the Client model."""

    def test_valid_instantiation(self):
        invoicing_contact = Contact(
            first_name="Sam",
            last_name="Lowry",
            email="sam.lowry@miniinf.gov",
            company="Ministry of Information",
        )
        client = Client(
            name="Ministry of Information",
            invoicing_contact=invoicing_contact,
        )
        db_engine = create_engine("sqlite:///")
        SQLModel.metadata.create_all(db_engine)
        with Session(db_engine) as session:
            session.add(invoicing_contact)
            session.add(client)
            session.commit()
        with Session(db_engine) as session:
            retrieved = session.exec(select(Client)).first()
            assert retrieved is not None
            assert retrieved.name == "Ministry of Information"

    def test_missing_name(self):
        """Test that a ValidationError is raised when the name is missing."""
        with pytest.raises(ValidationError):
            Client.validate(dict())

        try:
            client = Client.validate(dict())
        except ValidationError as ve:
            for error in ve.errors():
                field_name = error.get("loc")[0]
                error_message = error.get("msg")
                assert field_name == "name"

    def test_missing_fields_instantiation(self):
        with pytest.raises(ValidationError):
            Client.validate(dict())


class TestContract:
    """Tests for the Contract model."""

    def test_valid_instantiation(self):
        client = Client(name="Ministry of Information")
        contract = Contract.validate(
            dict(
                title="Project X Contract",
                client=client,
                signature_date=datetime.date(2022, 10, 1),
                start_date=datetime.date(2022, 10, 2),
                end_date=datetime.date(2022, 12, 31),
                rate=100,
                is_completed=False,
                currency="USD",
                VAT_rate=0.19,
                unit=TimeUnit.hour,
                units_per_workday=8,
                volume=100,
                term_of_payment=31,
                billing_cycle=Cycle.monthly,
            )
        )
        assert store_and_retrieve(contract)

    def test_missing_fields_instantiation(self):
        with pytest.raises(ValidationError):
            Contract.validate(dict())


class TestProject:
    """Tests for the Project model."""

    def test_valid_instantiation(self):
        client = Client(name="Ministry of Information")
        contract = Contract(
            title="Project X Contract",
            client=client,
            signature_date=datetime.date(2022, 10, 1),
            start_date=datetime.date(2022, 10, 2),
            end_date=datetime.date(2022, 12, 31),
            rate=100,
            is_completed=False,
            currency="USD",
            VAT_rate=0.19,
            unit=TimeUnit.hour,
            units_per_workday=8,
            volume=100,
            term_of_payment=31,
            billing_cycle=Cycle.monthly,
        )
        project = Project.validate(
            dict(
                title="Project X",
                description="The description of Project X",
                tag="#project_x",
                start_date=datetime.date(2022, 10, 2),
                end_date=datetime.date(2022, 12, 31),
                contract=contract,
            )
        )
        assert store_and_retrieve(project)

    def test_missing_fields_instantiation(self):
        with pytest.raises(ValidationError):
            Project.validate(dict())

    def test_invalid_tag_instantiation(self):
        with pytest.raises(ValidationError):
            Project.validate(
                dict(
                    title="Project X",
                    description="The description of Project X",
                    tag="project_x",
                    start_date=datetime.date(2022, 10, 2),
                    end_date=datetime.date(2022, 12, 31),
                )
            )


# ---------------------------------------------------------------------------
# Deletion guard / referential integrity tests
# ---------------------------------------------------------------------------


def _make_engine_with_fk(tmp_path):
    """Create an in-memory SQLite engine with FK enforcement enabled."""
    import sqlalchemy as sa

    db_path = tmp_path / "integrity_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    sa.event.listen(
        engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys = ON")
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(session):
    """Insert a minimal entity chain: Address -> Contact -> Client -> Contract -> Project."""
    from tuttle.model import Cycle, TimeUnit

    addr = Address(
        street="1st St", number="1", city="C", postal_code="00000", country="US"
    )
    contact = Contact(
        first_name="Jane", last_name="Doe", email="jane@example.com", address=addr
    )
    client = Client(name="Acme", invoicing_contact=contact)
    contract = Contract(
        title="Support",
        client=client,
        signature_date=datetime.date(2024, 1, 1),
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        rate=100,
        currency="EUR",
        billing_cycle=Cycle.monthly,
        unit=TimeUnit.hour,
    )
    project = Project(
        title="Website",
        description="Build a website",
        tag="#website",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 6, 30),
        contract=contract,
    )
    session.add(project)
    session.commit()
    session.refresh(contact)
    session.refresh(client)
    session.refresh(contract)
    session.refresh(project)
    return contact, client, contract, project


class TestDeletionGuards:
    """Verify that entities referenced by others cannot be deleted."""

    def test_cannot_delete_contact_used_by_client(self, tmp_path):
        engine = _make_engine_with_fk(tmp_path)
        with Session(engine, expire_on_commit=False) as s:
            contact, client, _, _ = _seed(s)
        with Session(engine) as s:
            c = s.get(Contact, contact.id)
            s.delete(c)
            with pytest.raises(Exception):
                s.commit()

    def test_cannot_delete_client_used_by_contract(self, tmp_path):
        engine = _make_engine_with_fk(tmp_path)
        with Session(engine, expire_on_commit=False) as s:
            _, client, _, _ = _seed(s)
        with Session(engine) as s:
            c = s.get(Client, client.id)
            s.delete(c)
            with pytest.raises(Exception):
                s.commit()

    def test_cannot_delete_contract_used_by_project(self, tmp_path):
        engine = _make_engine_with_fk(tmp_path)
        with Session(engine, expire_on_commit=False) as s:
            _, _, contract, _ = _seed(s)
        with Session(engine) as s:
            c = s.get(Contract, contract.id)
            s.delete(c)
            with pytest.raises(Exception):
                s.commit()

    def test_can_delete_project_without_references(self, tmp_path):
        engine = _make_engine_with_fk(tmp_path)
        with Session(engine, expire_on_commit=False) as s:
            _, _, _, project = _seed(s)
        with Session(engine) as s:
            p = s.get(Project, project.id)
            s.delete(p)
            s.commit()
            assert s.get(Project, project.id) is None

    def test_can_delete_leaf_to_root_sequentially(self, tmp_path):
        """Deleting in reverse dependency order must succeed."""
        engine = _make_engine_with_fk(tmp_path)
        with Session(engine, expire_on_commit=False) as s:
            contact, client, contract, project = _seed(s)
        with Session(engine) as s:
            s.delete(s.get(Project, project.id))
            s.commit()
        with Session(engine) as s:
            s.delete(s.get(Contract, contract.id))
            s.commit()
        with Session(engine) as s:
            s.delete(s.get(Client, client.id))
            s.commit()
        with Session(engine) as s:
            s.delete(s.get(Contact, contact.id))
            s.commit()
