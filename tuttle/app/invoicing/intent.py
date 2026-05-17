import datetime as _dt
import textwrap
from datetime import date
from pathlib import Path
from typing import Mapping, Optional, Type, Union

from loguru import logger
from pandas import DataFrame

from ..auth.data_source import UserDataSource
from ..auth.intent import AuthIntent
from ..core.abstractions import Intent
from ..core.intent_result import IntentResult
from ..preferences.intent import PreferencesIntent
from ..preferences.model import (
    DEFAULT_INVOICE_NUMBER_SCHEME,
    DEFAULT_INVOICE_TEMPLATE,
    INVOICE_NUMBER_SCHEMES,
    INVOICE_TEMPLATES,
    PreferencesStorageKeys,
    SUPPORTED_INVOICE_LANGUAGES,
)
from ..projects.intent import ProjectsIntent
from ..timetracking.data_source import TimeTrackingDataFrameSource
from ..timetracking.intent import TimeTrackingIntent
from ...app_db import AppDatabase
from ... import invoicing, mail, os_functions, rendering, timetracking
from ...model import Invoice, InvoiceItem, Project, Timesheet, User

from .data_source import InvoicingDataSource


class InvoicingIntent(Intent):
    """Invoicing CRUD, creation orchestration, and status toggles."""

    def __init__(self, client_storage=None):
        self._projects_intent = ProjectsIntent()
        self._invoicing_data_source = InvoicingDataSource()
        self._timetracking_data_source = TimeTrackingDataFrameSource()
        self._user_data_source = UserDataSource()
        self._auth_intent = AuthIntent()
        self._preferences_intent = PreferencesIntent()
        self._timetracking_intent = TimeTrackingIntent()

    # -- RPC-facing CRUD -------------------------------------------------------

    def get_all(self) -> IntentResult:
        return self._invoicing_data_source.get_all_invoices()

    def delete(self, id) -> IntentResult:
        return self.delete_invoice_by_id(id)

    def create(
        self,
        project_id,
        invoice_date,
        from_date,
        to_date,
        render=True,
        manual_quantity=None,
    ) -> IntentResult:
        """Orchestrates invoice creation: resolve project, read prefs, delegate."""
        proj_result = self._projects_intent.get_by_id(project_id)
        if not proj_result.was_intent_successful:
            return proj_result
        app_db = AppDatabase()
        language = app_db.get_setting(PreferencesStorageKeys.language_key.value) or "en"
        template_name = (
            app_db.get_setting(PreferencesStorageKeys.invoice_template_key.value)
            or DEFAULT_INVOICE_TEMPLATE
        )
        number_scheme = (
            app_db.get_setting(PreferencesStorageKeys.invoice_number_scheme_key.value)
            or DEFAULT_INVOICE_NUMBER_SCHEME
        )

        def _to_date(v):
            return v if isinstance(v, date) else _dt.date.fromisoformat(v)

        return self.create_invoice(
            invoice_date=_to_date(invoice_date),
            project=proj_result.data,
            from_date=_to_date(from_date),
            to_date=_to_date(to_date),
            render=render,
            manual_quantity=manual_quantity,
            language=language,
            template_name=template_name,
            number_scheme=number_scheme,
        )

    # -- Status toggles (accept id, fetch internally) --------------------------

    def _toggle(self, field: str, invoice_id: int) -> IntentResult:
        result = self._invoicing_data_source.get_invoice_by_id(invoice_id)
        if not result.was_intent_successful or not result.data:
            return IntentResult(
                was_intent_successful=False, error_msg="Invoice not found"
            )
        return getattr(self, f"toggle_invoice_{field}_status")(result.data)

    def send_mail(self, id) -> IntentResult:
        result = self._invoicing_data_source.get_invoice_by_id(id)
        if not result.was_intent_successful or not result.data:
            return IntentResult(
                was_intent_successful=False, error_msg="Invoice not found"
            )
        return self.send_invoice_by_mail(result.data)

    def toggle_sent(self, id) -> IntentResult:
        return self._toggle("sent", id)

    def toggle_paid(self, id) -> IntentResult:
        return self._toggle("paid", id)

    def toggle_cancelled(self, id) -> IntentResult:
        return self._toggle("cancelled", id)

    # -- Static data -----------------------------------------------------------

    def available_templates(self) -> IntentResult:
        return IntentResult(was_intent_successful=True, data=INVOICE_TEMPLATES)

    def available_languages(self) -> IntentResult:
        return IntentResult(
            was_intent_successful=True, data=SUPPORTED_INVOICE_LANGUAGES
        )

    def available_number_schemes(self) -> IntentResult:
        return IntentResult(was_intent_successful=True, data=INVOICE_NUMBER_SCHEMES)

    def get_user(self) -> IntentResult[User]:
        user = self._user_data_source.get_user()
        return IntentResult(was_intent_successful=True, data=user)

    def get_active_projects_as_map(self) -> Mapping[int, Project]:
        return self._projects_intent.get_active_as_map()

    def get_invoices_for_project_as_map(self, project_id) -> IntentResult:
        result = self._invoicing_data_source.get_invoices_for_project(project_id)
        if result.was_intent_successful and result.data:
            invoices_list = result.data
            invoices_map = {invoice.id: invoice for invoice in invoices_list}
            return invoices_map
        else:
            if not result.was_intent_successful:
                result.log_message_if_any()
            return {}

    def get_all_invoices_as_map(self) -> Mapping[int, Invoice]:
        result = self._invoicing_data_source.get_all_invoices()
        if result.was_intent_successful:
            invoices = result.data
            invoices_map = {invoice.id: invoice for invoice in invoices}
            return invoices_map
        else:
            result.log_message_if_any()
            return {}

    def delete_invoice_by_id(self, invoice_id) -> IntentResult[None]:
        """Delete an invoice by id (cascades to timesheets and invoice items)."""
        try:
            self._invoicing_data_source.delete_invoice_by_id(invoice_id)
            return IntentResult(was_intent_successful=True)
        except Exception as ex:
            logger.error(f"Could not delete invoice with id {invoice_id}.")
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg="Could not delete invoice.",
            )

    def create_invoice(
        self,
        invoice_date: date,
        project: Project,
        from_date: date,
        to_date: date,
        render: bool = True,
        manual_quantity: Optional[float] = None,
        language: str = "en",
        template_name: Optional[str] = None,
        number_scheme: str = DEFAULT_INVOICE_NUMBER_SCHEME,
    ) -> IntentResult[Invoice]:
        """Create a new invoice.

        When *manual_quantity* is provided the invoice is built directly from
        the given quantity and the contract rate, without requiring imported
        time-tracking data.  Otherwise the existing time-tracking flow is
        used.
        """
        logger.info(f"Creating invoice for {project.title}...")
        user = self._user_data_source.get_user()
        try:
            invoice_number = self._invoicing_data_source.generate_invoice_number(
                invoice_date, scheme=number_scheme
            )

            if manual_quantity is not None:
                contract = project.contract
                item = InvoiceItem(
                    start_date=from_date,
                    end_date=to_date,
                    quantity=manual_quantity,
                    unit=contract.unit.value if contract.unit else "hour",
                    unit_price=contract.rate,
                    description=project.title,
                    VAT_rate=contract.VAT_rate,
                )
                invoice = Invoice(
                    date=invoice_date,
                    number=invoice_number,
                    contract=contract,
                    project=project,
                    items=[item],
                )
            else:
                # ── Time-tracking path (existing) ─────────────────
                timetracking_data = self._timetracking_data_source.get_data_frame()
                timesheet: Timesheet = timetracking.generate_timesheet(
                    timetracking_data,
                    project,
                    from_date,
                    to_date,
                )
                invoice: Invoice = invoicing.generate_invoice(
                    date=invoice_date,
                    number=invoice_number,
                    timesheets=[timesheet],
                    contract=project.contract,
                    project=project,
                )
                timesheet.invoice = invoice

            if render:
                if manual_quantity is None and "timesheet" in locals():
                    try:
                        rendering.render_timesheet(
                            user=user,
                            timesheet=timesheet,
                            out_dir=Path.home() / ".tuttle" / "Timesheets",
                            only_final=True,
                        )
                    except Exception as ex:
                        logger.error(
                            f"Error rendering timesheet for {project.title}: {ex}"
                        )
                        logger.exception(ex)

                resolved_template = template_name or DEFAULT_INVOICE_TEMPLATE
                if not template_name:
                    tmpl_result = (
                        self._preferences_intent.get_preferred_invoice_template()
                    )
                    if tmpl_result.was_intent_successful and tmpl_result.data:
                        resolved_template = tmpl_result.data

                try:
                    rendering.render_invoice(
                        user=user,
                        invoice=invoice,
                        out_dir=Path.home() / ".tuttle" / "Invoices",
                        template_name=resolved_template,
                        only_final=True,
                        language=language,
                    )
                except Exception as ex:
                    logger.error(f"Error rendering invoice for {project.title}: {ex}")
                    logger.exception(ex)

            self._invoicing_data_source.save_invoice(invoice)
            return IntentResult(
                was_intent_successful=True,
                data=invoice,
            )
        except ValueError:
            error_message = (
                f"No time tracking data found for project "
                f"'{project.title}' between {from_date} and {to_date}."
            )
            logger.error(error_message)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_message,
            )
        except Exception as ex:
            error_message = "Failed to create invoice."
            logger.error(error_message)
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_message,
            )

    def update_invoice(
        self,
        invoice: Invoice,
    ) -> IntentResult:
        result: IntentResult = self._invoicing_data_source.save_invoice(invoice)
        if not result.was_intent_successful:
            result.log_message_if_any()
            result.error_msg = "Failed to update the invoice."
            # TODO re-load old invoice
        return result

    def send_invoice_by_mail(self, invoice: Invoice) -> IntentResult[None]:
        """attempts to trigger the mail client to send the intent as attachment"""
        invoice_path = Path.home() / ".tuttle" / "Invoices" / invoice.file_name
        if not invoice.rendered:
            return IntentResult(
                was_intent_successful=False,
                error_msg="The invoice has not been rendered.",
            )
        if not invoice_path.exists():
            return IntentResult(
                was_intent_successful=False,
                error_msg=f"The invoice file {invoice_path} does not exist.",
            )
        try:
            user = self._user_data_source.get_user()
            # open email client with message pre-filled
            client = invoice.contract.client
            contact = client.invoicing_contact if client else None
            greeting = contact.name if contact and contact.name else client.name
            recipient = contact.email if contact and contact.email else None

            if not recipient:
                return IntentResult(
                    was_intent_successful=False,
                    error_msg="No contact email available for this client.",
                )

            email_body = textwrap.dedent(
                f"""\
Dear {greeting},

Please find attached the invoice for {invoice.project.title}.

Best regards,
{user.name}"""
            )
            mail.compose_email(
                to=recipient,
                subject=f"Invoice {invoice.number}",
                body=email_body,
                attachment_paths=[invoice_path],
            )

            return IntentResult(
                was_intent_successful=True,
            )
        except Exception as ex:
            logger.error(f"❌ Error sending invoice by mail: {ex}")
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to send the invoice by mail. ",
            )

    def generate_invoice_doc(self, invoice: Invoice) -> IntentResult:
        """TODO Attempts to generate the invoice as a pdf and open the location"""
        return IntentResult(was_intent_successful=False, error_msg="Not implemented")

    def toggle_invoice_sent_status(self, invoice: Invoice) -> IntentResult[Invoice]:
        """
        Toggles the "sent" status of an invoice and updates it in the data source.

        Parameters:
            invoice (Invoice):
                The invoice object whose "sent" status will be toggled.

        Returns:
            IntentResult[Invoice]:
                An IntentResult object containing the updated invoice, or old invoice if update was not successful.
        """
        try:
            invoice.sent = not invoice.sent
            self._invoicing_data_source.save_invoice(invoice)
            return IntentResult(
                was_intent_successful=True,
                data=invoice,
            )
        except Exception as ex:
            logger.error(f"❌ Error toggling invoice sent status: {ex}")
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to toggle the invoice sent status. ",
            )

    def toggle_invoice_paid_status(self, invoice: Invoice) -> IntentResult[Invoice]:
        """
        Toggles the "paid" status of an invoice and updates it in the data source.

        Parameters:
            invoice (Invoice):
                The invoice object whose "paid" status will be toggled.

        Returns:
            IntentResult[Invoice]:
                An IntentResult object containing the updated invoice, or old invoice if update was not successful.
        """
        try:
            invoice.paid = not invoice.paid
            self._invoicing_data_source.save_invoice(invoice)
            return IntentResult(
                was_intent_successful=True,
                data=invoice,
            )
        except Exception as ex:
            logger.error(f"❌ Error toggling invoice paid status: {ex}")
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to toggle the invoice paid status. ",
            )

    def toggle_invoice_cancelled_status(
        self, invoice: Invoice
    ) -> IntentResult[Invoice]:
        """
        Toggles the "cancelled" status of an invoice and updates it in the data source.

        Parameters:
            invoice (Invoice):
                The invoice object whose "cancelled" status will be toggled.

        Returns:
            IntentResult[Invoice]:
                An IntentResult object containing the updated invoice, or old invoice if update was not successful.
        """
        try:
            invoice.cancelled = not invoice.cancelled
            self._invoicing_data_source.save_invoice(invoice)
            return IntentResult(
                was_intent_successful=True,
                data=invoice,
            )
        except Exception as ex:
            logger.error(f"❌ Error toggling invoice cancelled status: {ex}")
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to toggle the invoice cancelled status. ",
            )

    def view_invoice(self, invoice: Invoice) -> IntentResult[Path]:
        """Resolve the PDF path for an invoice."""
        if not invoice.rendered:
            return IntentResult(
                was_intent_successful=False,
                error_msg="The invoice has not been rendered.",
            )
        try:
            pdf_path = Path().home() / ".tuttle" / "Invoices" / invoice.file_name
            if not pdf_path.exists():
                return IntentResult(
                    was_intent_successful=False,
                    error_msg=f"Invoice file not found: {pdf_path.name}",
                )
            return IntentResult(was_intent_successful=True, data=pdf_path)
        except Exception as ex:
            error_message = f"Failed to open the invoice: {ex.__class__.__name__}"
            logger.error(error_message)
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_message,
            )

    def view_timesheet_for_invoice(self, invoice: Invoice) -> IntentResult[Path]:
        """Resolve the PDF path for the timesheet belonging to an invoice."""
        try:
            timesheet = self._invoicing_data_source.get_timesheet_for_invoice(invoice)
            timesheet_path = (
                Path().home() / ".tuttle" / "Timesheets" / f"{timesheet.prefix}.pdf"
            )
            if not timesheet_path.exists():
                return IntentResult(
                    was_intent_successful=False,
                    error_msg=f"Timesheet file not found: {timesheet_path.name}",
                )
            return IntentResult(was_intent_successful=True, data=timesheet_path)
        except ValueError as ve:
            logger.error(f"❌ Error getting timesheet for invoice: {ve}")
            logger.exception(ve)
            return IntentResult(was_intent_successful=False, error_msg=str(ve))
        except Exception as ex:
            error_message = f"Failed to open the timesheet: {ex.__class__.__name__}"
            logger.error(error_message)
            logger.exception(ex)
            return IntentResult(
                was_intent_successful=False,
                error_msg=error_message,
            )

    def get_time_tracking_data_as_dataframe(self) -> Optional[DataFrame]:

        result = self._timetracking_intent.get_timetracking_data()
        return result.data
