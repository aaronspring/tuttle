"""Schema management for Tuttle databases.

During development the SQLModel class definitions in model.py are the single
source of truth.  We simply call ``create_all`` which creates any missing
tables (and is a no-op for tables that already exist).

For destructive schema changes, delete the ``.db`` file first — the existing
``reset_database()`` flow already does this.

SQLite's ``CREATE TABLE IF NOT EXISTS`` does not add columns to existing
tables, so ``_migrate_add_columns`` runs ``ALTER TABLE … ADD COLUMN`` for
each column that is missing.
"""

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

import tuttle.model  # noqa: F401 — ensure all table classes are registered

_INVOICE_REMINDER_COLUMNS = {
    "document_type": "VARCHAR DEFAULT 'invoice'",
    "reminder_for_id": "INTEGER REFERENCES invoice(id)",
    "reminder_level": "INTEGER DEFAULT 0",
    "reminder_fee": "NUMERIC(12,2)",
    "reminder_due_date": "DATE",
}

_CLIENT_EINVOICE_COLUMNS = {
    "vat_number": "VARCHAR",
}


def _migrate_add_columns(engine) -> None:
    """Add missing columns to existing tables (safe for SQLite)."""
    insp = inspect(engine)
    table_names = insp.get_table_names()

    if "invoice" in table_names:
        existing = {col["name"] for col in insp.get_columns("invoice")}
        with engine.begin() as conn:
            for col_name, col_def in _INVOICE_REMINDER_COLUMNS.items():
                if col_name not in existing:
                    stmt = f"ALTER TABLE invoice ADD COLUMN {col_name} {col_def}"
                    conn.execute(text(stmt))
                    logger.info(f"Added column invoice.{col_name}")

    if "client" in table_names:
        existing = {col["name"] for col in insp.get_columns("client")}
        with engine.begin() as conn:
            for col_name, col_def in _CLIENT_EINVOICE_COLUMNS.items():
                if col_name not in existing:
                    stmt = f"ALTER TABLE client ADD COLUMN {col_name} {col_def}"
                    conn.execute(text(stmt))
                    logger.info(f"Added column client.{col_name}")


def ensure_schema(db_url: str) -> None:
    """Create all tables defined by SQLModel if they don't already exist."""
    engine = create_engine(db_url)
    try:
        SQLModel.metadata.create_all(engine)
        _migrate_add_columns(engine)
        logger.debug(f"Schema ensured for {db_url}")
    finally:
        engine.dispose()
