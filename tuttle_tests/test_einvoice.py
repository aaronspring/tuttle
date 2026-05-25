"""Tests for the ZUGFeRD / Factur-X e-invoice generation."""

import datetime
from decimal import Decimal

import pytest
from lxml import etree

from tuttle.einvoice import (
    build_zugferd_document,
    country_to_iso,
    serialize_zugferd_xml,
    unit_to_unece,
)
from tuttle.model import (
    Address,
    BankAccount,
    Client,
    Contract,
    Invoice,
    InvoiceItem,
    Project,
    User,
)
from tuttle.time import Cycle, TimeUnit


# -- Helper fixtures ----------------------------------------------------------


def _make_user() -> User:
    return User(
        name="Harry Tuttle",
        subtitle="Heating Engineer",
        email="mail@tuttle.example",
        VAT_number="DE123456789",
        address=Address(
            street="Hauptstraße",
            number="42",
            postal_code="10115",
            city="Berlin",
            country="Germany",
        ),
        bank_account=BankAccount(
            name="Business",
            IBAN="DE89370400440532013000",
            BIC="COBADEFFXXX",
        ),
    )


def _make_invoice() -> Invoice:
    client = Client(
        name="Central Services GmbH",
        vat_number="DE987654321",
        address=Address(
            street="Industriestraße",
            number="7",
            postal_code="80331",
            city="München",
            country="Germany",
        ),
    )
    contract = Contract(
        title="Heating Maintenance",
        client=client,
        start_date=datetime.date(2024, 1, 1),
        rate=Decimal("100.00"),
        currency="EUR",
        VAT_rate=Decimal("0.19"),
        unit=TimeUnit.hour,
        units_per_workday=8,
        term_of_payment=30,
        billing_cycle=Cycle.monthly,
    )
    project = Project(
        title="Q1 Maintenance",
        tag="#Maintenance",
        contract=contract,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 3, 31),
    )
    items = [
        InvoiceItem(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 31),
            quantity=40.0,
            unit="hour",
            unit_price=Decimal("100.00"),
            description="Heating system maintenance - January",
            VAT_rate=Decimal("0.19"),
        ),
        InvoiceItem(
            start_date=datetime.date(2024, 2, 1),
            end_date=datetime.date(2024, 2, 29),
            quantity=32.0,
            unit="hour",
            unit_price=Decimal("100.00"),
            description="Heating system maintenance - February",
            VAT_rate=Decimal("0.19"),
        ),
    ]
    return Invoice(
        number="2024-03-15-01",
        date=datetime.date(2024, 3, 15),
        contract=contract,
        project=project,
        items=items,
    )


# -- Unit tests: helpers ------------------------------------------------------


class TestCountryToISO:
    def test_full_name(self):
        assert country_to_iso("Germany") == "DE"

    def test_already_code(self):
        assert country_to_iso("DE") == "DE"
        assert country_to_iso("fr") == "FR"

    def test_fuzzy(self):
        assert country_to_iso("United States") == "US"

    def test_empty_default(self):
        assert country_to_iso("") == "DE"


class TestUnitToUNECE:
    def test_known_units(self):
        assert unit_to_unece("hour") == "HUR"
        assert unit_to_unece("hours") == "HUR"
        assert unit_to_unece("day") == "DAY"
        assert unit_to_unece("days") == "DAY"
        assert unit_to_unece("month") == "MON"
        assert unit_to_unece("unit") == "C62"

    def test_unknown_fallback(self):
        assert unit_to_unece("widgets") == "C62"


# -- Integration test: XML generation ----------------------------------------


class TestBuildZugferdDocument:
    def test_builds_valid_document(self):
        user = _make_user()
        invoice = _make_invoice()
        doc = build_zugferd_document(invoice, user, profile="EN16931")
        assert doc is not None
        assert str(doc.header.id) == "2024-03-15-01"
        assert str(doc.header.type_code) == "380"

    def test_serialize_produces_valid_xml(self):
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(invoice, user, profile="EN16931")

        assert xml_bytes is not None
        assert len(xml_bytes) > 0

        root = etree.fromstring(xml_bytes)
        assert root.tag is not None
        assert "CrossIndustryInvoice" in root.tag

    def test_xml_contains_seller_info(self):
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(invoice, user, profile="EN16931")
        xml_str = xml_bytes.decode("utf-8")

        assert "Harry Tuttle" in xml_str
        assert "DE123456789" in xml_str
        assert "DE89370400440532013000" in xml_str

    def test_xml_contains_buyer_info(self):
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(invoice, user, profile="EN16931")
        xml_str = xml_bytes.decode("utf-8")

        assert "Central Services GmbH" in xml_str
        assert "DE987654321" in xml_str

    def test_xml_contains_line_items(self):
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(invoice, user, profile="EN16931")
        xml_str = xml_bytes.decode("utf-8")

        assert "Heating system maintenance - January" in xml_str
        assert "Heating system maintenance - February" in xml_str

    def test_monetary_totals_correct(self):
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(invoice, user, profile="EN16931")
        xml_str = xml_bytes.decode("utf-8")

        # 40h + 32h = 72h @ 100 EUR = 7200 net; 19% VAT = 1368; total = 8568
        assert "7200" in xml_str
        assert "1368" in xml_str
        assert "8568" in xml_str

    def test_schema_validation_passes(self):
        """serialize with schema validation enabled should not raise."""
        user = _make_user()
        invoice = _make_invoice()
        xml_bytes = serialize_zugferd_xml(
            invoice, user, profile="EN16931", validate=True
        )
        assert len(xml_bytes) > 0

    def test_embed_in_pdf(self, tmp_path):
        """Full round-trip: generate a PDF, embed ZUGFeRD XML, verify output."""
        from pypdf import PdfWriter

        from tuttle.einvoice import embed_zugferd_in_pdf

        user = _make_user()
        invoice = _make_invoice()

        # Create a minimal valid PDF
        pdf_path = tmp_path / "test-invoice.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        original_size = pdf_path.stat().st_size
        embed_zugferd_in_pdf(
            pdf_path=str(pdf_path),
            invoice=invoice,
            user=user,
            profile="EN16931",
        )
        augmented_size = pdf_path.stat().st_size
        assert augmented_size > original_size
