"""Object model — the single source of truth for the database schema.

SCHEMA CHANGE WORKFLOW
======================
Any change to a SQLModel class in this file (new column, renamed field,
new table, new relationship) is a schema change. You MUST follow up with:

    1. just migrate "<describe change>"
       (alias for `alembic revision --autogenerate -m ...`)
    2. Review the generated script in tuttle/migrations/versions/
       — especially CHECK FOR drop_column + add_column PAIRS that
       represent renames; replace them with op.alter_column(...,
       new_column_name=...) to preserve data.
    3. Commit model.py AND the new migration script TOGETHER.

DO NOT edit user databases manually. DO NOT add ALTER TABLE strings here
or elsewhere — Alembic derives all DDL from SQLModel.metadata.

See tuttle/migrations/README.md and .cursor/rules/schema-migrations.mdc
for the full rationale.
"""

from typing import Literal, Optional, List, Dict, Type
from pydantic import constr, BaseModel, condecimal
from enum import Enum
import datetime
import textwrap

import re
import datetime
import decimal
import email
import hashlib
import string
import textwrap
import uuid
from decimal import Decimal
from enum import Enum

import pandas
import sqlalchemy

# from pydantic import str
from pydantic import BaseModel, condecimal, constr, validator
from sqlmodel import SQLModel, Field, Relationship, Constraint


from pathlib import Path

from .app.core.formatting import fmt_currency
from .dev import deprecated
from .time import Cycle, TimeUnit

DocumentType = Literal["invoice", "reminder"]


class RpcMixin:
    """Mixin that auto-serialises SQLModel objects for RPC transport.

    Class-level declarations::

        __rpc_relationships__ = ("address",)                       # full dump
        __rpc_relationships__ = {"projects": ("id", "title")}      # field projection
        __rpc_computed__      = ("sum", "total", "status")         # @property values
    """

    __rpc_relationships__: tuple | dict = ()
    __rpc_computed__: tuple = ()

    def to_rpc_dict(self, _depth: int = 2) -> dict:
        d = self.model_dump()
        for prop in self.__rpc_computed__:
            d[prop] = getattr(self, prop, None)
        if _depth <= 0:
            return d
        rels = self.__rpc_relationships__
        items = rels.items() if isinstance(rels, dict) else ((r, None) for r in rels)
        for rel_name, projection in items:
            value = getattr(self, rel_name, None)
            if value is None:
                continue
            if isinstance(value, list):
                d[rel_name] = [_project(v, projection, _depth - 1) for v in value]
            else:
                d[rel_name] = _project(value, projection, _depth - 1)
        return d


def _project(obj, projection, depth: int):
    if projection:
        return {f: getattr(obj, f, None) for f in projection}
    if hasattr(obj, "to_rpc_dict"):
        return obj.to_rpc_dict(_depth=depth)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def help(model_class: Type[BaseModel]):
    return pandas.DataFrame(
        (
            (field_name, field.field_info.description)
            for field_name, field in Contract.__fields__.items()
        ),
        columns=["field name", "field description"],
    )


def to_dataframe(items: List[Type[BaseModel]]) -> pandas.DataFrame:
    """Convert list of pydantic model items to DataFrame.

    Args:
        items (List[Type[BaseModel]]): [description]

    Returns:
        pandas.DataFrame: [description]
    """
    return pandas.DataFrame.from_records([item.dict() for item in items])


def OneToOneRelationship(back_populates):
    """Define a relationship as one-to-one."""
    return Relationship(
        back_populates=back_populates,
        sa_relationship_kwargs={"uselist": False, "lazy": "subquery"},
    )


class Address(RpcMixin, SQLModel, table=True):
    """Postal address."""

    id: Optional[int] = Field(default=None, primary_key=True)
    street: str = Field(default="", description="Street name")
    number: str = Field(default="", description="House or building number")
    city: str = Field(default="", description="City or town")
    postal_code: str = Field(default="", description="Postal / ZIP code")
    country: str = Field(default="", description="Country name")
    users: List["User"] = Relationship(back_populates="address")
    contacts: List["Contact"] = Relationship(back_populates="address")
    clients: List["Client"] = Relationship(back_populates="address")

    @property
    def printed(self):
        """Print address in common format."""
        return (
            f"{self.street} {self.number}\n"
            f"{self.postal_code} {self.city}\n"
            f"{self.country}"
        )

    @property
    def html(self):
        """Print address in common format."""
        return (
            f"{self.street} {self.number}<br>"
            f"{self.postal_code} {self.city}<br>"
            f"{self.country}"
        )

    @property
    def is_empty(self) -> bool:
        """True if all fields are empty."""
        return all(
            [
                not self.street,
                not self.number,
                not self.city,
                not self.postal_code,
                not self.country,
            ]
        )


class User(RpcMixin, SQLModel, table=True):
    """User of the application, a freelancer."""

    __rpc_relationships__ = ("address",)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    subtitle: str = Field(
        description="Role or job title of the user, e.g. 'Freelance web developer'."
    )
    website: Optional[str] = Field(
        default=None,
        description="URL of the user's website.",
    )
    email: str = Field(description="Email address of the user.")
    phone_number: Optional[str] = Field(
        default=None,
        description="Phone number of the user.",
    )
    profile_photo_path: Optional[str] = Field(default=None)
    address_id: Optional[int] = Field(default=None, foreign_key="address.id")
    address: Optional[Address] = Relationship(
        back_populates="users",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    operating_country: str = Field(
        default="Germany",
        description="Country whose tax system and currency the freelancer operates under.",
    )
    VAT_number: Optional[str] = Field(
        default=None,
        description="Value Added Tax number of the user, legally required for invoices.",
    )
    # User 1:1* ICloudAccount
    icloud_account_id: Optional[int] = Field(
        default=None, foreign_key="icloudaccount.id"
    )
    icloud_account: Optional["ICloudAccount"] = Relationship(back_populates="user")
    # User 1:1* Google Account
    # TODO: Google account
    # google_account_id: Optional[int] = Field(
    #     default=None, foreign_key="googleaccount.id"
    # )
    # google_account: Optional["GoogleAccount"] = Relationship(back_populates="user")
    # User 1:1 business BankAccount
    bank_account_id: Optional[int] = Field(default=None, foreign_key="bankaccount.id")
    bank_account: Optional["BankAccount"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # TODO: path to logo image
    # logo: Optional[str] = Field(default=None)

    @property
    def bank_account_not_set(self) -> bool:
        """True if bank account is not set."""
        if not self.bank_account:
            return True
        if (
            not self.bank_account.BIC
            or not self.bank_account.IBAN
            or not self.bank_account.name
        ):
            return True
        return False


class ICloudAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str
    user: User = OneToOneRelationship(back_populates="icloud_account")


class GoogleAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str
    # user: User = OneToOneRelationship(back_populates="google_account")


class Bank(SQLModel, table=True):
    """A bank."""

    id: Optional[int] = Field(default=None, primary_key=True)
    BLZ: str  # TODO: add type / validator


class BankAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    IBAN: str
    BIC: str
    # username: str  # online banking user name
    user: User = Relationship(back_populates="bank_account")


class Contact(RpcMixin, SQLModel, table=True):
    """An entry in the address book."""

    __rpc_relationships__ = ("address",)

    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: Optional[str] = Field(default=None, description="First / given name")
    last_name: Optional[str] = Field(default=None, description="Last / family name")
    company: Optional[str] = Field(
        default=None, description="Company or organisation name"
    )
    email: Optional[str] = Field(default=None, description="Email address")
    address_id: Optional[int] = Field(default=None, foreign_key="address.id")
    address: Optional[Address] = Relationship(
        back_populates="contacts", sa_relationship_kwargs={"lazy": "subquery"}
    )
    invoicing_contact_of: List["Client"] = Relationship(
        back_populates="invoicing_contact",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )
    # post address

    # VALIDATORS
    @validator("email")
    def email_validator(cls, v):
        """Validate email address format."""
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("Not a valid email address")
        return v

    @property
    def name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        elif self.company:
            return self.company
        else:
            return None

    def print_address(self, address_only: bool = False):
        """Print address in common format."""
        if self.address is None:
            return ""

        if address_only:
            return textwrap.dedent(
                f"""
                {self.address.street} {self.address.number}
                {self.address.postal_code} {self.address.city}
                {self.address.country}"""
            )

        return textwrap.dedent(
            f"""
        {self.name}
        {self.company}
        {self.address.street} {self.address.number}
        {self.address.postal_code} {self.address.city}
        {self.address.country}
        """
        )


class Client(RpcMixin, SQLModel, table=True):
    """A client the freelancer has contracted with.

    A client can be a company or a natural person.  It may optionally
    have an invoicing contact (a person to address invoices to) and/or
    its own address.
    """

    __rpc_relationships__ = ("invoicing_contact", "address")
    __rpc_computed__ = ("invoice_recipient_name",)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(
        description="Name of the client.",
        sa_column_kwargs={"unique": True},
    )
    vat_number: Optional[str] = Field(
        default=None,
        description="VAT identification number of the client (for e-invoicing).",
    )
    # Client n:1 Address (optional, for direct invoicing)
    address_id: Optional[int] = Field(default=None, foreign_key="address.id")
    address: Optional[Address] = Relationship(
        back_populates="clients",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # Client n:1 invoicing Contact (optional)
    invoicing_contact_id: Optional[int] = Field(
        default=None, foreign_key="contact.id", ondelete="RESTRICT"
    )
    invoicing_contact: Optional[Contact] = Relationship(
        back_populates="invoicing_contact_of",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    contracts: List["Contract"] = Relationship(
        back_populates="client",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )

    @property
    def invoice_recipient_name(self) -> str:
        """Name to use on invoices: contact name if available, else client name."""
        if self.invoicing_contact and self.invoicing_contact.name:
            return self.invoicing_contact.name
        return self.name

    @property
    def invoice_recipient_address(self) -> Optional["Address"]:
        """Address for invoices: prefer contact address, fall back to client address."""
        if self.invoicing_contact and self.invoicing_contact.address:
            return self.invoicing_contact.address
        return self.address


CONTRACT_DEFAULT_VAT_RATE = 0.19


class Contract(RpcMixin, SQLModel, table=True):
    """A contract defines the business conditions of a project"""

    __rpc_relationships__ = {
        "client": None,
        "projects": ("id", "title"),
        "invoices": ("id",),
    }

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(
        description="Short description of the contract.",
        sa_column_kwargs={"unique": True},
    )
    client: Client = Relationship(
        back_populates="contracts", sa_relationship_kwargs={"lazy": "subquery"}
    )
    signature_date: Optional[datetime.date] = Field(
        default=None,
        description="Date on which the contract was signed",
    )
    start_date: datetime.date = Field(
        description="Date from which the contract is valid",
    )
    end_date: Optional[datetime.date] = Field(
        description="Date until which the contract is valid",
        default=None,
    )
    # Contract n:1 Client
    client_id: Optional[int] = Field(
        default=None,
        foreign_key="client.id",
        ondelete="RESTRICT",
    )
    rate: condecimal(decimal_places=2) = Field(
        description="Rate of remuneration",
    )
    is_completed: bool = Field(
        default=False, description="flag marking if contract has been completed"
    )
    currency: str = Field(description="Currency code, e.g. EUR or USD")
    VAT_rate: Decimal = Field(
        description="VAT rate applied to the contractual rate.",
        default=CONTRACT_DEFAULT_VAT_RATE,  # TODO: configure by country?
    )
    unit: TimeUnit = Field(
        description="Unit of time tracked. The rate applies to this unit.",
        sa_column=sqlalchemy.Column(sqlalchemy.Enum(TimeUnit)),
        default=TimeUnit.hour,
    )
    units_per_workday: int = Field(
        description="How many units of time (e.g. hours) constitute a whole work day?",
        default=8,
    )
    volume: Optional[int] = Field(
        description="Number of units agreed on",
    )
    term_of_payment: Optional[int] = Field(
        description="How many days after receipt of invoice this invoice is due.",
        default=31,
    )
    billing_cycle: Cycle = Field(
        sa_column=sqlalchemy.Column(sqlalchemy.Enum(Cycle)),
        description="How often is an invoice sent?",
    )
    projects: List["Project"] = Relationship(
        back_populates="contract",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )
    invoices: List["Invoice"] = Relationship(
        back_populates="contract",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )

    @property
    def volume_as_time(self):
        return self.volume * self.unit.to_timedelta()

    @property
    def unit_duration(self) -> datetime.timedelta:
        """Real-world duration of one contractual billing unit.

        For ``unit=hour`` this is 1 hour. For ``unit=day`` it is
        ``units_per_workday`` hours — a contractual "day" is a *work* day,
        not a calendar day.  Used by ``invoicing.generate_invoice`` to
        convert tracked time to billable quantity.
        """
        if self.unit == TimeUnit.hour:
            return datetime.timedelta(hours=1)
        if self.unit == TimeUnit.day:
            return datetime.timedelta(hours=self.units_per_workday)
        raise ValueError(f"Unsupported contract unit: {self.unit}")

    def is_active(self) -> bool:
        """Check if contract is active.A contract is active if it is not completed and the end date is in the future."""
        if self.is_completed:
            return False
        if self.is_upcoming():
            return False
        if self.end_date:
            today = datetime.date.today()
            return self.end_date > today
        else:
            return True

    def is_upcoming(self) -> bool:
        today = datetime.date.today()
        return self.start_date > today

    def get_status(self, default: str = "All") -> str:
        if self.is_active():
            return "Active"
        elif self.is_upcoming():
            return "Upcoming"
        elif self.is_completed:
            return "Completed"
        else:
            # default
            return default


class Project(RpcMixin, SQLModel, table=True):
    """A project is a group of contract work for a client."""

    __rpc_relationships__ = ("contract",)

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(
        description="A short, unique title",
        sa_column_kwargs={"unique": True},
    )
    description: str = Field(
        description="A longer description of the project",
    )
    tag: str = Field(
        description="A unique tag, starting with a # symbol",
        sa_column_kwargs={"unique": True},
    )
    start_date: datetime.date = Field(description="Project start date")
    end_date: datetime.date = Field(description="Project end date")
    is_completed: bool = Field(
        default=False, description="marks if the project is completed"
    )
    stage: Optional[str] = Field(
        default=None,
        description="Explicit pipeline stage override: Lead, Offer, Upcoming, Active, or Completed. "
        "When set, takes precedence over the date-derived status.",
    )
    # Project m:n Contract
    contract_id: Optional[int] = Field(
        default=None, foreign_key="contract.id", ondelete="RESTRICT"
    )
    contract: Contract = Relationship(
        back_populates="projects",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # Project 1:n Timesheet
    timesheets: List["Timesheet"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )
    # Project 1:n Invoice
    invoices: List["Invoice"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"lazy": "subquery", "passive_deletes": "all"},
    )

    def __repr__(self):
        return f"Project(id={self.id}, title={self.title}, tag={self.tag})"

    # PROPERTIES
    @property
    def client(self) -> Optional[Client]:
        if self.contract:
            return self.contract.client
        else:
            return None

    # VALIDATORS
    @validator("tag")
    def validate_tag(cls, v):
        if not re.match(r"^#\S+$", v):
            raise ValueError(
                "Tag must start with a # symbol and not contain any punctuation or whitespace."
            )
        return v

    @deprecated
    def get_brief_description(self):
        if len(self.description) <= 108:
            return self.description
        else:
            return f"{self.description[0:108]}..."

    def is_active(self) -> bool:
        """Is the project active? A project is active if it is not completed and if the end date is in the future."""
        if self.is_completed:
            return False
        if self.is_upcoming():
            return False
        if self.end_date:
            today = datetime.date.today()
            return self.end_date >= today
        else:
            return True

    def is_upcoming(self) -> bool:
        today = datetime.date.today()
        return self.start_date > today

    # FIXME: replace string literals with enum
    def get_status(self, default: str = "") -> str:
        if self.is_active():
            return "Active"
        elif self.is_upcoming():
            return "Upcoming"
        elif self.is_completed:
            return "Completed"
        else:
            # default
            return default


class TimeTrackingItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # TimeTrackingItem n : 1 TimeSheet
    timesheet_id: Optional[int] = Field(
        default=None, foreign_key="timesheet.id", ondelete="CASCADE"
    )
    timesheet: Optional["Timesheet"] = Relationship(back_populates="items")
    #
    begin: datetime.datetime = Field(description="Start time of the time interval.")
    end: datetime.datetime = Field(description="End time of the time interval.")
    duration: datetime.timedelta = Field(description="Duration of the time interval.")
    title: str = Field(description="A short description of the time interval.")
    tag: str = Field(
        description="A short tag to identify the project the time interval belongs to."
    )
    description: Optional[str] = Field(
        description="A longer description of the time interval."
    )


class Timesheet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    date: datetime.date = Field(description="The date of creation of the timesheet")
    period_start: datetime.date = Field(
        description="The start date of the period covered by the timesheet."
    )
    period_end: datetime.date = Field(
        description="The end date of the period covered by the timesheet."
    )

    # Timesheet n:1 Project
    project_id: Optional[int] = Field(
        default=None, foreign_key="project.id", ondelete="RESTRICT"
    )
    project: Project = Relationship(
        back_populates="timesheets",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # invoice: "Invoice" = Relationship(back_populates="timesheet")
    # period: str
    comment: Optional[str] = Field(description="A comment on the timesheet.")
    items: List[TimeTrackingItem] = Relationship(
        back_populates="timesheet",
        sa_relationship_kwargs={
            "lazy": "subquery",
            "cascade": "all, delete",  # delete all items when deleting a timesheet
        },
    )

    rendered: bool = Field(
        default=False,
        description="Whether the Timesheet has been rendered as a PDF.",
    )

    # Timesheet n:1 Invoice
    invoice_id: Optional[int] = Field(
        default=None, foreign_key="invoice.id", ondelete="CASCADE"
    )
    invoice: Optional["Invoice"] = Relationship(
        back_populates="timesheets",
        sa_relationship_kwargs={"lazy": "subquery"},
    )

    # class Config:
    #     arbitrary_types_allowed = True

    def __repr__(self):
        return f"Timesheet(id={self.id}, tag={self.project.tag}, period_start={self.period_start}, period_end={self.period_end})"

    @property
    def prefix(self) -> str:
        return f"{self.project.tag[1:]}-{self.period_start.strftime('%Y-%m-%d')}-{self.period_end.strftime('%Y-%m-%d')}"

    @property
    def total(self) -> datetime.timedelta:
        """Sum of time in timesheet."""
        total_time = self.table["duration"].sum()
        return total_time

    @property
    def table(self) -> pandas.DataFrame:
        """items as DataFrame"""
        return to_dataframe(self.items)

    @property
    def empty(self) -> bool:
        return len(self.items) == 0


class Invoice(RpcMixin, SQLModel, table=True):
    """An invoice or payment reminder.

    Reminders reuse the same table (manual STI) with ``document_type``
    as the discriminator.  A reminder references its predecessor via
    ``reminder_for_id``, forming a singly-linked chain back to the
    original invoice.
    """

    __rpc_relationships__ = ("contract", "project", "items")
    __rpc_computed__ = (
        "sum",
        "VAT_total",
        "total",
        "due_date",
        "effective_due_date",
        "status",
        "file_name",
        "sum_formatted",
        "vat_total_formatted",
        "total_formatted",
        "pdf_path",
        "is_reminder",
        "reminder_chain_head_id",
        "has_timesheet",
        "timesheet_pdf_path",
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    number: Optional[str] = Field(description="The invoice number. Auto-generated.")
    date: datetime.date = Field(
        description="The date of the invoice",
    )

    # -- Document type discriminator (manual STI) --------------------------

    document_type: str = Field(
        default="invoice",
        description="'invoice' for a regular invoice, 'reminder' for a payment reminder.",
        schema_extra={"enum": ["invoice", "reminder"]},
    )

    # -- Reminder-specific fields (NULL for regular invoices) --------------

    reminder_for_id: Optional[int] = Field(
        default=None,
        foreign_key="invoice.id",
        description="FK to the predecessor invoice/reminder in a reminder chain.",
    )
    reminder_level: int = Field(
        default=0,
        description="0 = original invoice, 1 = 1st reminder, 2 = 2nd, etc.",
    )
    reminder_fee: Optional[Decimal] = Field(
        default=None,
        sa_column=sqlalchemy.Column(sqlalchemy.Numeric(12, 2), nullable=True),
        description="Optional surcharge added on this reminder.",
    )
    reminder_due_date: Optional[datetime.date] = Field(
        default=None,
        description="New payment deadline set by this reminder.",
    )

    # -- Relationships -----------------------------------------------------

    # Invoice n:1 Contract
    contract_id: Optional[int] = Field(
        default=None, foreign_key="contract.id", ondelete="RESTRICT"
    )
    contract: Contract = Relationship(
        back_populates="invoices",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # Invoice n:1 Project
    project_id: Optional[int] = Field(
        default=None, foreign_key="project.id", ondelete="RESTRICT"
    )
    project: Project = Relationship(
        back_populates="invoices",
        sa_relationship_kwargs={"lazy": "subquery"},
    )
    # Invoice 1:n Timesheet
    timesheets: List[Timesheet] = Relationship(
        back_populates="invoice",
        sa_relationship_kwargs={
            "lazy": "subquery",
            "cascade": "all, delete",
        },
    )

    # Self-referencing: reminder chain
    reminder_for: Optional["Invoice"] = Relationship(
        back_populates="reminders",
        sa_relationship_kwargs={
            "remote_side": "Invoice.id",
            "foreign_keys": "[Invoice.reminder_for_id]",
            "lazy": "subquery",
        },
    )
    reminders: List["Invoice"] = Relationship(
        back_populates="reminder_for",
        sa_relationship_kwargs={
            "foreign_keys": "[Invoice.reminder_for_id]",
            "lazy": "subquery",
        },
    )

    # -- Status flags ------------------------------------------------------

    sent: Optional[bool] = Field(default=False)
    paid: Optional[bool] = Field(default=False)
    cancelled: Optional[bool] = Field(
        default=False,
        description="If the invoice has been cancelled, e.g. because it was incorrect.",
    )
    items: List["InvoiceItem"] = Relationship(
        back_populates="invoice",
        sa_relationship_kwargs={
            "lazy": "subquery",
            "cascade": "all, delete",
        },
    )
    rendered: bool = Field(
        default=False,
        description="Whether the invoice has been rendered as a PDF.",
    )

    def __repr__(self):
        return f"Invoice(id={self.id}, number={self.number}, date={self.date}, type={self.document_type})"

    # -- Computed properties -----------------------------------------------

    @property
    def is_reminder(self) -> bool:
        return self.document_type == "reminder"

    @property
    def sum(self) -> Decimal:
        """Sum over all invoice items."""
        s = sum([item.subtotal for item in self.items])
        return Decimal(s)

    @property
    def VAT_total(self) -> Decimal:
        """Sum of VAT over all invoice items."""
        s = sum(item.VAT for item in self.items)
        return Decimal(round(s, 2))

    @property
    def total(self) -> Decimal:
        """Total invoiced amount, including reminder fee if present."""
        t = self.sum + self.VAT_total
        if self.reminder_fee:
            t += self.reminder_fee
        return Decimal(t)

    @property
    def due_date(self) -> Optional[datetime.date]:
        """Original due date derived from contract payment terms."""
        if self.contract and self.contract.term_of_payment:
            return self.date + datetime.timedelta(days=self.contract.term_of_payment)
        return None

    @property
    def effective_due_date(self) -> Optional[datetime.date]:
        """The due date that applies: reminder_due_date if set, else contract-derived."""
        if self.reminder_due_date:
            return self.reminder_due_date
        return self.due_date

    @property
    def status(self) -> str:
        """Derived invoice status: draft, cancelled, paid, overdue, or sent."""
        if self.cancelled:
            return "cancelled"
        if self.paid:
            return "paid"
        if self.sent:
            due = self.effective_due_date
            if due and due < datetime.date.today():
                return "overdue"
            return "sent"
        return "draft"

    @property
    def reminder_chain_head_id(self) -> Optional[int]:
        """Walk reminder_for up to the root invoice and return its id.

        Uses the eagerly-loaded ``reminder_for`` relationship when available,
        but falls back to ``reminder_for_id`` to avoid DetachedInstanceError.
        """
        if not self.is_reminder:
            return self.id
        node = self
        visited: set[int] = set()
        while node.reminder_for_id and node.reminder_for_id not in visited:
            visited.add(node.id)
            try:
                parent = node.reminder_for
            except Exception:
                return node.reminder_for_id
            if parent is None:
                return node.reminder_for_id
            node = parent
        return node.id

    @property
    def client(self):
        return self.contract.client

    @property
    def prefix(self):
        """A string that can be used as the prefix of a file name, or a folder name."""
        client_suffix = ""
        if self.client:
            client_suffix = "-".join(self.client.name.lower().split())
        base = f"{self.number}-{client_suffix}"
        if self.is_reminder:
            return f"{base}-M{self.reminder_level}"
        return base

    @property
    def file_name(self):
        """A string that can be used as a file name."""
        return f"{self.prefix}.pdf"

    @property
    def sum_formatted(self) -> str:
        currency = self.contract.currency if self.contract else "EUR"
        return fmt_currency(self.sum, currency)

    @property
    def vat_total_formatted(self) -> str:
        currency = self.contract.currency if self.contract else "EUR"
        return fmt_currency(self.VAT_total, currency)

    @property
    def total_formatted(self) -> str:
        currency = self.contract.currency if self.contract else "EUR"
        return fmt_currency(self.total, currency)

    @property
    def pdf_path(self) -> Optional[str]:
        if not self.rendered:
            return None
        p = Path.home() / ".tuttle" / "Invoices" / self.file_name
        return str(p) if p.exists() else None

    @property
    def has_timesheet(self) -> bool:
        """True iff the invoice was created from time-tracking data."""
        return bool(self.timesheets)

    @property
    def timesheet_pdf_path(self) -> Optional[str]:
        """Filesystem path of the timesheet PDF, if it has been rendered."""
        if not self.timesheets:
            return None
        ts = self.timesheets[0]
        if not ts.rendered:
            return None
        p = Path.home() / ".tuttle" / "Timesheets" / f"{ts.prefix}.pdf"
        return str(p) if p.exists() else None


class InvoiceItem(RpcMixin, SQLModel, table=True):
    __rpc_computed__ = ("subtotal", "subtotal_formatted", "unit_price_formatted")

    id: Optional[int] = Field(default=None, primary_key=True)
    # date and time
    start_date: datetime.date = Field(description="Start date of the invoice item.")
    end_date: Optional[datetime.date] = Field(
        description="End date of the invoice item."
    )
    #
    quantity: float
    unit: str
    unit_price: Decimal
    description: str
    VAT_rate: Decimal
    # invoice
    invoice_id: Optional[int] = Field(
        default=None, foreign_key="invoice.id", ondelete="CASCADE"
    )
    invoice: Invoice = Relationship(
        back_populates="items",
        sa_relationship_kwargs={"lazy": "subquery"},
    )

    @property
    def subtotal(self) -> Decimal:
        return Decimal(str(self.quantity)) * self.unit_price

    @property
    def subtotal_formatted(self) -> str:
        return fmt_currency(self.subtotal)

    @property
    def unit_price_formatted(self) -> str:
        return fmt_currency(self.unit_price)

    @property
    def VAT(self) -> Decimal:
        """VAT for the invoice item."""
        return self.subtotal * self.VAT_rate


# class Payment(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     # invoice: Invoice = Relationship(back_populates="payment")


class TimelineItem(SQLModel, table=True):
    """An item that appears in the freelancer's timeline."""

    id: Optional[int] = Field(default=None, primary_key=True)
    time: datetime.datetime = Field(
        sa_column=sqlalchemy.Column(
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
        )
    )
    content: str


class FinancialGoal(SQLModel, table=True):
    """A financial target the freelancer wants to reach."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(
        description="Short description of the goal, e.g. 'Yearly revenue'."
    )
    target_amount: Decimal = Field(
        description="Target amount in the user's currency.",
        sa_column=sqlalchemy.Column(sqlalchemy.Numeric(12, 2), nullable=False),
    )
    target_date: datetime.date = Field(
        description="Date by which the goal should be reached.",
    )
    is_reached: bool = Field(
        default=False,
        description="Whether the goal has been reached.",
    )


class RecurringExpense(SQLModel, table=True):
    """A regular operating expense that reduces the freelancer's spendable income.

    Examples: health insurance, professional liability insurance, accounting software.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(description="Short label, e.g. 'Health Insurance'.")
    amount: Decimal = Field(
        description="Amount per period in the given currency.",
        sa_column=sqlalchemy.Column(sqlalchemy.Numeric(12, 2), nullable=False),
    )
    currency: str = Field(default="EUR", description="ISO 4217 currency code.")
    period: Cycle = Field(
        sa_column=sqlalchemy.Column(sqlalchemy.Enum(Cycle), nullable=False),
        description="How often this expense recurs.",
    )
    category: str = Field(
        default="operating",
        description="Category tag: 'insurance', 'operating', 'professional', 'other'.",
    )
