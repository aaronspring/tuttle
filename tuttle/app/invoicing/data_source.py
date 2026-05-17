from typing import List, Optional, Type, Union

import datetime

from loguru import logger
import sqlmodel

from ..core.abstractions import SQLModelDataSourceMixin
from ..core.intent_result import IntentResult

from ...model import Invoice, Project, Timesheet


class InvoicingDataSource(SQLModelDataSourceMixin):
    """Handles manipulation of the Invoice model in the database"""

    def __init__(self):
        super().__init__()

    def get_invoices_for_project(self, project_id) -> IntentResult[List[Invoice]]:
        """TODO Get all invoices associated with a given project

        Returns:
            IntentResult:
                was_intent_successful : bool
                data : list[Invoice] was_intent_successful else None
                log_message  : str  if an error or exception occurs
                exception : Exception if an exception occurs
        """
        try:
            return IntentResult(
                was_intent_successful=False,
                log_message="NotImplementedError @InvoicingDataSource.get_invoices_for_project",
            )
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                log_message=f"Exception raised @TimeTrackingDataSource.get_invoices_for_project {e.__class__.__name__}",
                exception=e,
            )

    def get_invoice_by_id(self, invoice_id: int) -> IntentResult[Optional[Invoice]]:
        """Fetch a single invoice by primary key."""
        try:
            invoice = self.query_by_id(Invoice, invoice_id)
            return IntentResult(was_intent_successful=True, data=invoice)
        except Exception as ex:
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"Invoice with id={invoice_id} not found.",
                log_message=f"InvoicingDataSource.get_invoice_by_id({invoice_id}): {ex}",
                exception=ex,
            )

    def get_all_invoices(self) -> IntentResult[List[Invoice]]:
        """Get all existing invoices

        Returns:
            IntentResult:
                was_intent_successful : bool
                data : list[Invoice] was_intent_successful else None
                log_message  : str  if an error or exception occurs
                exception : Exception if an exception occurs
        """
        try:
            invoices = self.query(Invoice)
            return IntentResult(
                was_intent_successful=True,
                data=invoices,
            )
        except Exception as ex:
            return IntentResult(
                was_intent_successful=False,
                log_message=f"Exception raised @InvoicingDataSource.get_all_invoices {ex}",
                exception=ex,
            )

    def delete_invoice_by_id(self, invoice_id):
        """Deletes an invoice by id

        Args:
            invoice_id (int): the id of the invoice to delete
        """
        self.delete_by_id(Invoice, invoice_id)

    def save_invoice(
        self,
        invoice: Invoice,
    ):
        """Creates or updates an invoice with given invoice and project info"""
        logger.info(f"Saving invoice {invoice}")
        self.store(invoice)

    def save_timesheet(self, timesheet: Timesheet):
        """Creates or updates a timesheet"""
        self.store(timesheet)

    def get_timesheet_for_invoice(self, invoice: Invoice) -> Timesheet:
        """Get the timesheet associated with an invoice

        Args:
            invoice (Invoice): the invoice to get the timesheet for

        Returns:
            Optional[Timesheet]: the timesheet associated with the invoice
        """
        if not len(invoice.timesheets) > 0:
            raise ValueError(
                f"invoice {invoice.id} has no timesheets associated with it"
            )
        if len(invoice.timesheets) > 1:
            raise ValueError(
                f"invoice {invoice.id} has more than one timesheet associated with it: {invoice.timesheets}"
            )
        timesheet = invoice.timesheets[0]
        return timesheet

    def generate_invoice_number(
        self, date: datetime.date, scheme: str = "daily"
    ) -> str:
        """Generate a sequential invoice number using the given scheme.

        Schemes:
          daily  — YYYY-MM-DD-NN  (sequence resets each day)
          yearly — YYYY-NN        (sequence resets each year)
          plain  — NN             (never resets)

        Finds the max existing sequence suffix to avoid collisions after
        deletions.  Sequence numbers are zero-padded to at least 2 digits.
        """
        if scheme == "daily":
            prefix = date.strftime("%Y-%m-%d")
        elif scheme == "yearly":
            prefix = date.strftime("%Y")
        elif scheme == "plain":
            prefix = ""
        else:
            prefix = date.strftime("%Y-%m-%d")

        with self.create_session() as session:
            if prefix:
                invoices = session.exec(
                    sqlmodel.select(Invoice).where(
                        Invoice.number.startswith(f"{prefix}-")  # type: ignore[union-attr]
                    )
                ).all()
            else:
                invoices = session.exec(sqlmodel.select(Invoice)).all()

            max_seq = 0
            for inv in invoices:
                if not inv.number:
                    continue
                try:
                    seq = (
                        int(inv.number.rsplit("-", 1)[-1])
                        if prefix
                        else int(inv.number)
                    )
                    max_seq = max(max_seq, seq)
                except (ValueError, IndexError):
                    continue

            next_seq = max_seq + 1
            if prefix:
                return f"{prefix}-{next_seq:02d}"
            return f"{next_seq:02d}"
