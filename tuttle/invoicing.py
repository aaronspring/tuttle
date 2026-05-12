"""Invoicing."""

from typing import List, Optional, Dict
import datetime
from pathlib import Path
import shutil


import pandas
import datetime

from .model import InvoiceItem, Invoice, Contract, User, Project
from .timetracking import Timesheet


def generate_invoice(
    timesheets: List[Timesheet],
    contract: Contract,
    project: Project,
    number: str,
    date: datetime.date = datetime.date.today(),
) -> Invoice:
    invoice = Invoice(
        date=date,
        contract=contract,
        project=project,
        number=number,
    )
    for timesheet in timesheets:
        total_hours = timesheet.total / pandas.Timedelta("1h")
        item = InvoiceItem(
            invoice=invoice,
            start_date=timesheet.table["begin"].min().date(),
            end_date=timesheet.table["end"].max().date(),
            quantity=total_hours,
            unit="hour",
            unit_price=timesheet.project.contract.rate,
            VAT_rate=contract.VAT_rate,
            description=timesheet.title,
        )

    return invoice


def generate_invoice_email(
    invoice: Invoice,
    user: User,
) -> Optional[Dict]:
    """Generate an email with the invoice attached.

    Returns None when no contact email is available.
    """
    client = invoice.client
    contact = client.invoicing_contact if client else None
    greeting = contact.first_name if contact and contact.first_name else client.name
    recipient = contact.email if contact and contact.email else None

    if not recipient:
        return None

    body = f"""
    Dear {greeting}

    Please find attached the invoice number {invoice.number}.

    Best regards
    {user.name}
    """

    email = {
        "subject": f"Invoice {invoice.number}",
        "body": body,
        "recipient": recipient,
    }
    return email
