from typing import Callable, List, Optional

import calendar as _calendar
import datetime as _dt
from datetime import datetime, timedelta, date
from decimal import Decimal
from pathlib import Path

from flet import (
    AlertDialog,
    Alignment,
    Border,
    BorderRadius,
    BorderSide,
    ClipBehavior,
    Column,
    Container,
    Icon,
    IconButton,
    Icons,
    Image,
    ListTile,
    ListView,
    Padding,
    ProgressRing,
    ResponsiveRow,
    Row,
    ScrollMode,
    Text,
    TextOverflow,
    TextStyle,
    Control,
)

from ..core import utils, views
from ..core.abstractions import DialogHandler, TView, TViewParams
from ..core.intent_result import IntentResult
from loguru import logger
from pandas import DataFrame
from ..res import colors, dimens, fonts, res_utils

from ...model import Invoice, Project, User
from ...os_functions import render_pdf_pages

from .intent import InvoicingIntent


# ── Helpers ──────────────────────────────────────────────────


def _is_overdue(invoice: Invoice) -> bool:
    """Return True when the invoice is past its due date and still unpaid."""
    if invoice.paid or invoice.cancelled:
        return False
    try:
        due = invoice.due_date
    except Exception:
        return False
    return due is not None and due < date.today()


def _status_color(invoice: Invoice) -> str:
    """Return a left-stripe colour summarising the invoice status."""
    if invoice.cancelled:
        return colors.text_muted
    if invoice.paid:
        return colors.success
    if _is_overdue(invoice):
        return colors.danger
    if invoice.sent:
        return colors.accent
    return colors.text_muted  # draft / unsent


# ── Metric card (for the summary bar) ────────────────────────


class _MetricCard(Container):
    """Small KPI card showing a label + value + optional sub-text."""

    def __init__(
        self,
        label: str,
        value: str,
        color: str = colors.text_primary,
        sub: str = "",
    ):
        super().__init__(
            bgcolor=colors.bg_surface,
            border=Border.all(dimens.CARD_BORDER_WIDTH, colors.border),
            border_radius=dimens.RADIUS_LG,
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_MD, vertical=dimens.SPACE_SM
            ),
            expand=True,
            content=Column(
                spacing=2,
                controls=[
                    Text(
                        label.upper(),
                        size=fonts.OVERLINE_SIZE,
                        color=colors.text_muted,
                        weight=fonts.BOLDER_FONT,
                        style=TextStyle(letter_spacing=1.0),
                    ),
                    Text(
                        value,
                        size=fonts.HEADLINE_2_SIZE,
                        color=color,
                        weight=fonts.BOLD_FONT,
                    ),
                ]
                + (
                    [Text(sub, size=fonts.CAPTION_SIZE, color=colors.text_secondary)]
                    if sub
                    else []
                ),
            ),
        )


# ── Filter chip ──────────────────────────────────────────────


class _FilterChip(Container):
    """Compact pill-shaped filter chip."""

    def __init__(self, label: str, active: bool = False, on_click=None):
        self._label = label
        self._active = active
        super().__init__(
            bgcolor=colors.accent_muted if active else colors.bg_input,
            border_radius=dimens.RADIUS_PILL,
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XXS
            ),
            on_click=on_click,
            content=Text(
                label,
                size=fonts.CAPTION_SIZE,
                color=colors.text_inverse if active else colors.text_secondary,
                weight=fonts.BOLD_FONT if active else None,
            ),
        )


class PdfViewerPanel(Container):
    """Side panel that renders PDF pages as scrollable images."""

    def __init__(self, on_close: Callable):
        self._title_text = views.THeading(title="", size=fonts.HEADLINE_4_SIZE)
        self._close_btn = IconButton(
            icon=Icons.CLOSE,
            icon_size=dimens.ICON_SIZE,
            icon_color=colors.text_secondary,
            tooltip="Close",
            on_click=lambda e: on_close(),
        )
        self._header = Row(
            alignment=utils.SPACE_BETWEEN_ALIGNMENT,
            vertical_alignment=utils.CENTER_ALIGNMENT,
            controls=[self._title_text, self._close_btn],
        )
        self._page_list = ListView(expand=True, spacing=dimens.SPACE_XS)
        self._spinner = ProgressRing(width=32, height=32, stroke_width=3, visible=False)
        self._empty_label = views.TBodyText(
            "No PDF loaded",
            size=fonts.BODY_2_SIZE,
            color=colors.text_muted,
        )

        super().__init__(
            visible=False,
            expand=True,
            bgcolor=colors.bg_surface,
            border=Border(left=BorderSide(1, colors.border)),
            border_radius=BorderRadius(
                top_left=dimens.RADIUS_LG,
                bottom_left=dimens.RADIUS_LG,
                top_right=0,
                bottom_right=0,
            ),
            padding=Padding.all(dimens.SPACE_MD),
            content=Column(
                expand=True,
                controls=[
                    self._header,
                    Container(height=dimens.SPACE_XS),
                    self._spinner,
                    self._empty_label,
                    self._page_list,
                ],
            ),
        )

    def show_pdf(self, pdf_path: Path, title: str = "PDF"):
        """Render and display a PDF file."""
        self._title_text.title = title
        self._page_list.controls.clear()
        self._empty_label.visible = False
        self._spinner.visible = True
        self.visible = True

        try:
            pages = render_pdf_pages(str(pdf_path))
        except Exception:
            self._spinner.visible = False
            self._empty_label.value = "Failed to render PDF"
            self._empty_label.visible = True
            return

        self._spinner.visible = False
        for i, page_b64 in enumerate(pages):
            self._page_list.controls.append(
                Image(
                    src=page_b64,
                    fit="contain",
                    expand=True,
                )
            )

    def close(self):
        """Hide the panel and free rendered images."""
        self.visible = False
        self._page_list.controls.clear()
        self._empty_label.visible = True
        self._title_text.title = ""


class InvoicingEditorPopUp(DialogHandler, Column):
    """Pop up used for editing or creating an invoice

    Parameters:
        dialog_controller (Callable[[any, utils.AlertDialogControls], None]):
            The dialog controller
        on_submit (Callable):
            function that is called when the "Done" button is clicked
        projects_map (dict):
            a dictionary of projects mapped by their id
        invoice (Invoice, optional):
            an invoice object to edit, defaults to None if a new one is to be created
    """

    def __init__(
        self,
        dialog_controller: Callable[[any, utils.AlertDialogControls], None],
        on_submit: Callable,
        projects_map,
        invoice: Optional[Invoice] = None,
    ):
        # set the dimensions of the pop up
        pop_up_height = dimens.MIN_WINDOW_HEIGHT * 0.9
        pop_up_width = int(dimens.MIN_WINDOW_WIDTH * 0.8)

        # initialize the data
        today = datetime.today()
        yesterday = datetime.now() - timedelta(1)
        is_editing = invoice is not None
        self.invoice = invoice if is_editing else Invoice(number="", date=today)
        self.projects_as_map = projects_map
        project_options = [
            f"{id} {project.title}".strip()
            for id, project in self.projects_as_map.items()
        ]
        title = "Edit Invoice" if is_editing else "New Invoice"
        self.date_field = views.DateSelector(
            label="Invoice Date",
            initial_date=self.invoice.date,
        )
        self.from_date_field = views.DateSelector(
            label="From", initial_date=yesterday, label_color=colors.GRAY_COLOR
        )
        self.to_date_field = views.DateSelector(
            label="To", initial_date=today, label_color=colors.GRAY_COLOR
        )
        self.projects_dropdown = views.TDropDown(
            on_change=self.on_project_selected,
            label="Select project",
            items=project_options,
            show=not is_editing,
        )
        self.error_text = Text(
            "",
            color=colors.danger,
            size=fonts.BODY_2_SIZE,
            visible=False,
        )
        date_presets_row = Row(
            spacing=dimens.SPACE_XS,
            controls=[
                _FilterChip(
                    label=label, on_click=self._make_date_preset_handler(months_back)
                )
                for label, months_back in [
                    ("This Month", 0),
                    ("Last Month", 1),
                    ("2 Months Ago", 2),
                ]
            ],
        )
        dialog = AlertDialog(
            bgcolor=colors.bg_surface,
            content=Container(
                height=pop_up_height,
                width=pop_up_width,
                content=Column(
                    scroll=utils.AUTO_SCROLL,
                    controls=[
                        views.THeading(title=title, size=fonts.HEADLINE_4_SIZE),
                        views.Spacer(xs_space=True),
                        views.TTextField(
                            label="Invoice Number",
                            hint=self.invoice.number,
                            initial_value=self.invoice.number,
                            keyboard_type=utils.KEYBOARD_NONE,
                            show=is_editing,
                        ),
                        views.Spacer(xs_space=True),
                        self.date_field,
                        views.Spacer(xs_space=True),
                        self.projects_dropdown,
                        views.Spacer(),
                        views.SectionLabel("Date Range"),
                        date_presets_row,
                        self.from_date_field,
                        self.to_date_field,
                        views.Spacer(xs_space=True),
                        self.error_text,
                    ],
                ),
            ),
            actions=[
                views.TPrimaryButton(
                    label="Create", on_click=self.on_submit_btn_clicked
                ),
            ],
        )
        super().__init__(dialog=dialog, dialog_controller=dialog_controller)
        self.project = self.invoice.project if is_editing else None
        self.on_submit = on_submit

    def _make_date_preset_handler(self, months_back: int):
        """Return a click handler that sets the date range to a full month."""

        def _handler(e):
            today = date.today()
            year = today.year
            month = today.month - months_back
            while month < 1:
                month += 12
                year -= 1
            first_day = date(year, month, 1)
            last_day = date(year, month, _calendar.monthrange(year, month)[1])
            self.from_date_field.set_date(first_day)
            self.to_date_field.set_date(last_day)
            self.dialog.update()

        return _handler

    def _show_error(self, message: str):
        """Display an inline error message inside the dialog."""
        self.error_text.value = message
        self.error_text.visible = True
        self.dialog.update()

    def on_project_selected(self, e):
        selected_project = e.control.value
        # extract id from selected text
        id_ = int(selected_project.split(" ")[0])
        if id_ in self.projects_as_map:
            self.project = self.projects_as_map[id_]

    def on_submit_btn_clicked(self, e):
        """Called when the "Done" button is clicked"""
        date = self.date_field.get_date()
        if date:
            self.invoice.date = date
        from_date: Optional[datetime.date] = self.from_date_field.get_date()
        to_date: Optional[datetime.date] = self.to_date_field.get_date()

        if not self.project:
            self._show_error("Please select a project.")
            return
        if not from_date or not to_date:
            self._show_error("Please specify the date range.")
            return
        if to_date < from_date:
            self._show_error("The start date cannot be after the end date.")
            return

        self.close_dialog()
        self.on_submit(self.invoice, self.project, from_date, to_date)


class InvoicingListView(TView, Column):
    """The view for displaying the list of invoices"""

    # Filter keys
    _FILTER_ALL = "All"
    _FILTER_UNPAID = "Unpaid"
    _FILTER_OVERDUE = "Overdue"
    _FILTER_SENT = "Sent"
    _FILTER_PAID = "Paid"
    _FILTER_CANCELLED = "Cancelled"
    _FILTERS = [
        _FILTER_ALL,
        _FILTER_UNPAID,
        _FILTER_OVERDUE,
        _FILTER_SENT,
        _FILTER_PAID,
        _FILTER_CANCELLED,
    ]

    def __init__(self, params: TViewParams):
        super().__init__(params=params)
        self.intent = InvoicingIntent(client_storage=params.client_storage)
        self.invoices_to_display = {}
        self.contacts = {}
        self.active_projects = {}
        self.editor = None
        self._viewed_invoice_id: Optional[int] = None
        object.__setattr__(self, "time_tracking_data", None)
        object.__setattr__(self, "user", None)
        self.active_filter: str = self._FILTER_ALL

    def load_user_data(
        self,
    ):
        """Loads the user for payment info"""
        user_result: IntentResult = self.intent.get_user()
        if user_result.was_intent_successful:
            object.__setattr__(self, "user", user_result.data)
            self.is_user_missing_payment_info()
        else:
            self.show_snack(
                "Something went wrong! Failed to load your info.",
                is_error=True,
            )

    def is_user_missing_payment_info(
        self,
    ):
        """Checks if the user has set up their payment info.
        Displays a snack if they haven't."""
        if not self.user.VAT_number:
            self.show_snack(
                "You have not set up your VAT number yet. "
                "Please do so in the profile section",
                is_error=True,
            )
            return True
        if self.user.bank_account_not_set:
            self.show_snack(
                "You have not set up your payment information yet. "
                "Please do so in the profile section",
                is_error=True,
            )
            return True
        return False

    def parent_intent_listener(self, intent: str, data: any):
        """Handles the intent from the parent view"""
        if intent == res_utils.CREATE_INVOICE_INTENT:
            # create a new invoice
            if self.is_user_missing_payment_info():
                return  # can't create invoice without payment info
            if self.time_tracking_data is None:
                self.show_snack(
                    "You need to import time tracking data before invoices can be created.",
                    is_error=True,
                )
                return  # can't create invoice without time tracking data
            if self.editor is not None:
                self.editor.close_dialog()
            self.editor = InvoicingEditorPopUp(
                dialog_controller=self.dialog_controller,
                on_submit=self.on_save_invoice,
                projects_map=self.active_projects,
            )
            self.editor.open_dialog()

        elif intent == res_utils.RELOAD_INTENT:
            # reload the data
            self.initialize_data()

    def _apply_filter(self, invoices: List[Invoice]) -> List[Invoice]:
        """Return only invoices matching the active filter."""
        f = self.active_filter
        if f == self._FILTER_ALL:
            return invoices
        if f == self._FILTER_UNPAID:
            return [i for i in invoices if not i.paid and not i.cancelled]
        if f == self._FILTER_OVERDUE:
            return [i for i in invoices if _is_overdue(i)]
        if f == self._FILTER_SENT:
            return [i for i in invoices if i.sent and not i.paid and not i.cancelled]
        if f == self._FILTER_PAID:
            return [i for i in invoices if i.paid]
        if f == self._FILTER_CANCELLED:
            return [i for i in invoices if i.cancelled]
        return invoices

    def _on_filter_clicked(self, key: str):
        """Switch the active filter and refresh."""

        def _handler(e):
            self.active_filter = key
            self._rebuild_filter_chips()
            self.refresh_invoices()
            self.update_self()

        return _handler

    def _rebuild_filter_chips(self):
        """Rebuild the filter chips row to reflect the active selection."""
        self.filter_row.controls = [
            _FilterChip(
                label=f,
                active=(f == self.active_filter),
                on_click=self._on_filter_clicked(f),
            )
            for f in self._FILTERS
        ]

    def _update_summary(self):
        """Recompute and update the summary metric cards."""
        all_invoices = list(self.invoices_to_display.values())
        today = date.today()

        total_invoiced = Decimal(0)
        total_outstanding = Decimal(0)
        total_overdue = Decimal(0)
        overdue_count = 0
        total_paid = Decimal(0)

        for inv in all_invoices:
            try:
                amt = inv.total
            except Exception:
                amt = Decimal(0)
            total_invoiced += amt
            if inv.paid:
                total_paid += amt
            elif not inv.cancelled:
                total_outstanding += amt
                if _is_overdue(inv):
                    total_overdue += amt
                    overdue_count += 1

        # Determine a representative currency
        currency = ""
        for inv in all_invoices:
            try:
                currency = inv.contract.currency if inv.contract else ""
            except Exception:
                pass
            if currency:
                break

        def _fmt(v: Decimal) -> str:
            return f"{v:,.2f} {currency}".strip()

        self.metric_total.content.controls[1].value = _fmt(total_invoiced)
        self.metric_outstanding.content.controls[1].value = _fmt(total_outstanding)
        self.metric_outstanding.content.controls[1].color = (
            colors.accent if total_outstanding > 0 else colors.text_primary
        )
        overdue_label = _fmt(total_overdue)
        self.metric_overdue.content.controls[1].value = overdue_label
        self.metric_overdue.content.controls[1].color = (
            colors.danger if overdue_count > 0 else colors.text_primary
        )
        # Update sub text
        if len(self.metric_overdue.content.controls) > 2:
            self.metric_overdue.content.controls[2].value = (
                f"{overdue_count} invoice{'s' if overdue_count != 1 else ''}"
                if overdue_count > 0
                else ""
            )
        self.metric_paid.content.controls[1].value = _fmt(total_paid)

    def refresh_invoices(self):
        """Refreshes the invoices — sorted, filtered, grouped by month."""
        all_invoices = list(self.invoices_to_display.values())

        # Update summary metrics (always over the full set)
        self._update_summary()

        # Apply filter then sort newest-first
        filtered = self._apply_filter(all_invoices)
        filtered.sort(key=lambda i: i.date, reverse=True)

        self.invoices_list_control.controls.clear()

        if not filtered:
            self.no_invoices_control.visible = True
            return
        self.no_invoices_control.visible = False

        current_month_label = ""
        for invoice in filtered:
            # Month group header
            month_label = invoice.date.strftime("%B %Y")
            if month_label != current_month_label:
                current_month_label = month_label
                self.invoices_list_control.controls.append(
                    views.SectionLabel(current_month_label)
                )
            try:
                tile = InvoiceTile(
                    invoice=invoice,
                    on_delete_clicked=self.on_delete_invoice_clicked,
                    on_mail_invoice=self.on_mail_invoice,
                    on_view_invoice=self.on_view_invoice,
                    on_view_timesheet=self.on_view_timesheet,
                    toggle_paid_status=self.toggle_paid_status,
                    toggle_cancelled_status=self.toggle_cancelled_status,
                    toggle_sent_status=self.toggle_sent_status,
                    is_selected=invoice.id == self._viewed_invoice_id,
                )
            except Exception as ex:
                logger.error(f"Error while refreshing invoice: {ex}")
                logger.exception(ex)
                tile = ListTile(title=Text("Error while refreshing invoice"))
            self.invoices_list_control.controls.append(tile)

    def on_mail_invoice(self, invoice: Invoice):
        """Called when the user clicks send in the context menu of an invoice"""
        result = self.intent.send_invoice_by_mail(invoice)
        if not result.was_intent_successful:
            self.show_snack(result.error_msg, is_error=True)

    def on_view_invoice(self, invoice: Invoice):
        """Open the invoice PDF in the side panel."""
        result = self.intent.view_invoice(invoice)
        if not result.was_intent_successful:
            self.show_snack(result.error_msg, is_error=True)
            return
        self._viewed_invoice_id = invoice.id
        self.pdf_panel.show_pdf(result.data, title=f"Invoice {invoice.number}")
        self.refresh_invoices()
        self.update_self()

    def on_view_timesheet(self, invoice: Invoice):
        """Open the timesheet PDF in the side panel."""
        result = self.intent.view_timesheet_for_invoice(invoice)
        if not result.was_intent_successful:
            self.show_snack(result.error_msg, is_error=True)
            return
        self._viewed_invoice_id = invoice.id
        self.pdf_panel.show_pdf(result.data, title="Timesheet")
        self.refresh_invoices()
        self.update_self()

    def on_delete_invoice_clicked(self, invoice: Invoice):
        """Called when the user clicks delete in the context menu of an invoice"""
        if self.editor is not None:
            self.editor.close_dialog()
        self.editor = views.ConfirmDisplayPopUp(
            dialog_controller=self.dialog_controller,
            title="Are You Sure?",
            description=f"Are you sure you wish to delete this invoice?\nInvoice number: {invoice.number}",
            on_proceed=self.on_delete_confirmed,
            proceed_button_label="Yes! Delete",
            data_on_confirmed=invoice.id,
        )
        self.editor.open_dialog()

    def on_delete_confirmed(self, invoice_id):
        """Called when the user confirms the deletion of an invoice"""
        self.loading_indicator.visible = True
        self.update_self()
        result = self.intent.delete_invoice_by_id(invoice_id)
        is_error = not result.was_intent_successful
        msg = result.error_msg if is_error else "Invoice deleted!"
        self.show_snack(msg, is_error)
        if not is_error and invoice_id in self.invoices_to_display:
            del self.invoices_to_display[invoice_id]
            self.refresh_invoices()
        self.loading_indicator.visible = False
        self.update_self()

    def on_save_invoice(
        self,
        invoice: Invoice,
        project: Project,
        from_date: Optional[datetime.date],
        to_date: Optional[datetime.date],
    ):
        """Called when the user clicks on the submit button in the editor"""
        if not invoice:
            return  # this should never happen

        if not project:
            self.show_snack("Please specify the project")
            return

        if not from_date or not to_date:
            self.show_snack("Please specify the date range")
            return

        if to_date < from_date:
            self.show_snack("The start date cannot be after the end date")
            return

        is_updating = invoice.id is not None
        self.loading_indicator.visible = True
        self.update_self()
        if is_updating:
            # update the invoice
            result: IntentResult = self.intent.update_invoice(invoice=invoice)
        else:
            # create a new invoice
            result: IntentResult = self.intent.create_invoice(
                invoice_date=invoice.date,
                project=project,
                from_date=from_date,
                to_date=to_date,
            )

        if not result.was_intent_successful:
            self.show_snack(result.error_msg, True)
        else:
            self.update_invoice_from_intent_result(result)
            msg = (
                "The invoice has been updated"
                if is_updating
                else "A new invoice has been created"
            )
            self.show_snack(msg, False)
        self.loading_indicator.visible = False
        self.update_self()

    def toggle_paid_status(self, invoice: Invoice):
        """toggle the paid status of the invoice"""
        result: IntentResult = self.intent.toggle_invoice_paid_status(invoice)
        is_error = not result.was_intent_successful
        msg = result.error_msg if is_error else "Invoice status updated."
        self.show_snack(msg, is_error)
        if not is_error and result.data:
            self.update_invoice_from_intent_result(result)
        self.update_self()

    def toggle_sent_status(self, invoice: Invoice):
        """toggle the sent status of the invoice"""
        result: IntentResult = self.intent.toggle_invoice_sent_status(invoice)
        is_error = not result.was_intent_successful
        msg = result.error_msg if is_error else "Invoice status updated."
        self.show_snack(msg, is_error)
        if not is_error and result.data:
            self.update_invoice_from_intent_result(result)
        self.update_self()

    def update_invoice_from_intent_result(self, result: IntentResult[Invoice]):
        """update the invoice from an intent result data"""
        # update the invoice
        updated_invoice: Invoice = result.data
        self.invoices_to_display[updated_invoice.id] = updated_invoice
        self.refresh_invoices()

    def toggle_cancelled_status(self, invoice: Invoice):
        """toggle the cancelled status of the invoice"""
        result: IntentResult = self.intent.toggle_invoice_cancelled_status(invoice)
        is_error = not result.was_intent_successful
        msg = result.error_msg if is_error else "Invoice status updated."
        self.show_snack(msg, is_error)
        if not is_error and result.data:
            self.update_invoice_from_intent_result(result)
        self.update_self()

    def did_mount(self):
        """Called when the view is mounted"""
        self.initialize_data()

    def initialize_data(self):
        """initialize the data for the view"""
        self.mounted = True
        self.loading_indicator.visible = True
        self.active_projects = self.intent.get_active_projects_as_map()
        object.__setattr__(
            self,
            "time_tracking_data",
            self.intent.get_time_tracking_data_as_dataframe(),
        )
        self.load_user_data()
        self.invoices_to_display = self.intent.get_all_invoices_as_map()
        count = len(self.invoices_to_display)
        self.loading_indicator.visible = False
        if count == 0:
            self.no_invoices_control.visible = True
            self.summary_row.visible = False
            self.filter_row.visible = False
        else:
            self.no_invoices_control.visible = False
            self.summary_row.visible = True
            self.filter_row.visible = True
            self.refresh_invoices()
        self.update_self()

    def _close_pdf_panel(self):
        """Hide the PDF side panel and restore full-width list."""
        self._viewed_invoice_id = None
        self.pdf_panel.close()
        self.refresh_invoices()
        self.update_self()

    def build(self):
        """build the view"""
        self.loading_indicator = views.TProgressBar()

        # ── Empty state ──────────────────────────────────────
        self.no_invoices_control = Container(
            visible=False,
            padding=Padding.symmetric(vertical=dimens.SPACE_XXL),
            alignment=Alignment.CENTER,
            content=Column(
                horizontal_alignment=utils.CENTER_ALIGNMENT,
                spacing=dimens.SPACE_SM,
                controls=[
                    Icon(Icons.RECEIPT_LONG_OUTLINED, size=48, color=colors.text_muted),
                    views.TBodyText(
                        "No invoices yet",
                        size=fonts.HEADLINE_4_SIZE,
                        color=colors.text_secondary,
                    ),
                    views.TBodyText(
                        "Create your first invoice from a tracked project.",
                        size=fonts.BODY_2_SIZE,
                        color=colors.text_muted,
                    ),
                ],
            ),
        )

        # ── Summary metric cards ─────────────────────────────
        self.metric_total = _MetricCard(label="Total Invoiced", value="—")
        self.metric_outstanding = _MetricCard(
            label="Outstanding", value="—", color=colors.accent
        )
        self.metric_overdue = _MetricCard(
            label="Overdue", value="—", color=colors.danger, sub=""
        )
        self.metric_paid = _MetricCard(label="Paid", value="—", color=colors.success)
        self.summary_row = Row(
            spacing=dimens.SPACE_SM,
            visible=False,
            controls=[
                self.metric_total,
                self.metric_outstanding,
                self.metric_overdue,
                self.metric_paid,
            ],
        )

        # ── Filter chips ─────────────────────────────────────
        self.filter_row = Row(
            spacing=dimens.SPACE_XS,
            visible=False,
            controls=[
                _FilterChip(
                    label=f,
                    active=(f == self.active_filter),
                    on_click=self._on_filter_clicked(f),
                )
                for f in self._FILTERS
            ],
        )

        # ── Invoice list ─────────────────────────────────────
        self.invoices_list_control = ListView(
            expand=False,
            spacing=dimens.SPACE_XS,
        )

        # ── PDF side panel ───────────────────────────────────
        self.pdf_panel = PdfViewerPanel(on_close=self._close_pdf_panel)

        self.title_control = Row(
            controls=[
                views.THeading(title="Invoicing", size=fonts.HEADLINE_4_SIZE),
            ],
        )

        # Split layout: invoice list (left) + pdf panel (right)
        self.split_row = Row(
            expand=True,
            spacing=dimens.SPACE_SM,
            controls=[
                Container(self.invoices_list_control, expand=True),
                self.pdf_panel,
            ],
        )

        self.controls = [
            self.title_control,
            self.loading_indicator,
            self.summary_row,
            Container(height=dimens.SPACE_XS),
            self.filter_row,
            Container(height=dimens.SPACE_XS),
            self.no_invoices_control,
            self.split_row,
        ]

    def will_unmount(self):
        self.mounted = False
        if self.editor:
            self.editor.dimiss_open_dialogs()


class InvoiceTile(Container):
    """Rich invoice tile with left status stripe, quick-action buttons,
    net/VAT breakdown, due-date display, and overdue badge.
    """

    def __init__(
        self,
        invoice: Invoice,
        on_delete_clicked,
        on_mail_invoice,
        on_view_invoice,
        on_view_timesheet,
        toggle_paid_status,
        toggle_sent_status,
        toggle_cancelled_status,
        is_selected: bool = False,
    ):
        self.invoice = invoice
        self._is_selected = is_selected

        _project_title = invoice.project.title if invoice.project else ""
        _currency = invoice.contract.currency if invoice.contract else ""
        _client_name = (
            invoice.contract.client.name
            if invoice.contract and invoice.contract.client
            else ""
        )
        overdue = _is_overdue(invoice)
        stripe_color = _status_color(invoice)

        # ── Due date text ────────────────────────────────────
        due_parts: list[Control] = []
        try:
            due = invoice.due_date
            if due is not None:
                due_str = f'Due: {due.strftime("%d-%m-%Y")}'
                due_color = colors.danger if overdue else colors.text_secondary
                due_parts.append(
                    views.TBodyText(due_str, size=fonts.BODY_2_SIZE, color=due_color)
                )
        except Exception:
            pass
        if overdue:
            due_parts.append(
                Container(
                    bgcolor=colors.danger,
                    border_radius=dimens.RADIUS_SM,
                    padding=Padding.symmetric(horizontal=6, vertical=2),
                    content=Text(
                        "OVERDUE",
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_inverse,
                        weight=fonts.BOLDER_FONT,
                    ),
                )
            )

        # ── Context menu (less-common actions) ───────────────
        context = views.TContextMenu(
            on_click_delete=lambda e: on_delete_clicked(invoice),
            prefix_menu_items=[
                views.TPopUpMenuItem(
                    icon=Icons.CANCEL_OUTLINED,
                    txt="Mark as cancelled"
                    if not invoice.cancelled
                    else "Mark as not cancelled",
                    on_click=lambda e: toggle_cancelled_status(invoice),
                ),
                views.TPopUpMenuItem(
                    icon=Icons.VISIBILITY_OUTLINED,
                    txt="View Invoice PDF",
                    on_click=lambda e: on_view_invoice(invoice),
                ),
                views.TPopUpMenuItem(
                    icon=Icons.VISIBILITY_OUTLINED,
                    txt="View Timesheet",
                    on_click=lambda e: on_view_timesheet(invoice),
                ),
            ],
        )

        # ── Inline quick-action icon buttons ─────────────────
        paid_icon = Icons.PAYMENTS_OUTLINED if not invoice.paid else Icons.PAYMENTS
        paid_tooltip = "Mark as paid" if not invoice.paid else "Mark as unpaid"
        paid_color = colors.success if invoice.paid else colors.text_muted

        sent_icon = (
            Icons.MARK_EMAIL_READ_OUTLINED if invoice.sent else Icons.OUTGOING_MAIL
        )
        sent_tooltip = "Mark as not sent" if invoice.sent else "Send invoice"
        sent_color = colors.accent if invoice.sent else colors.text_muted

        quick_actions = Row(
            spacing=0,
            controls=[
                IconButton(
                    icon=paid_icon,
                    icon_size=dimens.ICON_SIZE,
                    icon_color=paid_color,
                    tooltip=paid_tooltip,
                    on_click=lambda e: toggle_paid_status(invoice),
                ),
                IconButton(
                    icon=sent_icon,
                    icon_size=dimens.ICON_SIZE,
                    icon_color=sent_color,
                    tooltip=sent_tooltip,
                    on_click=lambda e: (
                        on_mail_invoice(invoice)
                        if not invoice.sent
                        else toggle_sent_status(invoice)
                    ),
                ),
                context,
            ],
        )

        # ── Net / VAT / Total breakdown ──────────────────────
        try:
            net_val = f"{invoice.sum:,.2f}"
            vat_val = f"{invoice.VAT_total:,.2f}"
            total_val = f"{invoice.total:,.2f}"
        except Exception:
            net_val = vat_val = total_val = "—"

        amount_block = Column(
            spacing=0,
            horizontal_alignment=utils.END_ALIGNMENT,
            controls=[
                Text(
                    f"{total_val} {_currency}",
                    size=fonts.HEADLINE_4_SIZE,
                    weight=fonts.BOLD_FONT,
                    color=colors.text_primary,
                    no_wrap=True,
                ),
                Text(
                    f"Net {net_val}  ·  VAT {vat_val}",
                    size=fonts.CAPTION_SIZE,
                    color=colors.text_muted,
                    no_wrap=True,
                ),
            ],
        )

        # ── Status badges row ────────────────────────────────
        status_badges = Row(
            spacing=dimens.SPACE_SM,
            wrap=True,
            controls=[
                views.TStatusDisplay(txt="Paid", is_done=invoice.paid),
                views.TStatusDisplay(txt="Sent", is_done=invoice.sent),
            ]
            + (
                [views.TStatusDisplay(txt="Cancelled", is_done=True)]
                if invoice.cancelled
                else []
            )
            + due_parts,
        )

        # ── Assemble tile ────────────────────────────────────
        _bg = colors.accent_muted if is_selected else colors.bg_surface
        _border = (
            Border.all(2, colors.accent)
            if is_selected
            else Border.all(dimens.CARD_BORDER_WIDTH, colors.border)
        )
        super().__init__(
            bgcolor=_bg,
            border=_border,
            border_radius=dimens.RADIUS_LG,
            padding=Padding.all(0),
            clip_behavior=ClipBehavior.HARD_EDGE,
            on_hover=self._on_hover,
            content=Row(
                spacing=0,
                controls=[
                    # Left color stripe
                    Container(
                        width=4,
                        bgcolor=stripe_color,
                        border_radius=BorderRadius(
                            top_left=dimens.RADIUS_LG,
                            bottom_left=dimens.RADIUS_LG,
                            top_right=0,
                            bottom_right=0,
                        ),
                    ),
                    # Main content
                    Container(
                        expand=True,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        padding=Padding.only(
                            left=dimens.SPACE_SM,
                            right=dimens.SPACE_MD,
                            top=dimens.SPACE_SM,
                            bottom=dimens.SPACE_SM,
                        ),
                        content=Column(
                            spacing=dimens.SPACE_XXS,
                            controls=[
                                # Top row: number + client  |  amount + quick actions
                                Row(
                                    alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                                    vertical_alignment=utils.CENTER_ALIGNMENT,
                                    controls=[
                                        Row(
                                            spacing=dimens.SPACE_SM,
                                            expand=True,
                                            vertical_alignment=utils.CENTER_ALIGNMENT,
                                            controls=[
                                                views.TBodyText(
                                                    invoice.number or "—",
                                                    weight=fonts.BOLD_FONT,
                                                    no_wrap=True,
                                                ),
                                                Text(
                                                    _client_name,
                                                    color=colors.text_primary,
                                                    size=fonts.BODY_2_SIZE,
                                                    overflow=TextOverflow.ELLIPSIS,
                                                    no_wrap=True,
                                                    expand=True,
                                                ),
                                            ],
                                        ),
                                        Row(
                                            spacing=dimens.SPACE_SM,
                                            vertical_alignment=utils.CENTER_ALIGNMENT,
                                            controls=[
                                                amount_block,
                                                quick_actions,
                                            ],
                                        ),
                                    ],
                                ),
                                # Bottom row: date + due date + badges
                                Row(
                                    spacing=dimens.SPACE_MD,
                                    vertical_alignment=utils.CENTER_ALIGNMENT,
                                    controls=[
                                        views.TBodyText(
                                            f'{invoice.date.strftime("%d %b %Y")}',
                                            size=fonts.BODY_2_SIZE,
                                            color=colors.text_secondary,
                                            no_wrap=True,
                                        ),
                                        status_badges,
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _on_hover(self, e):
        if self._is_selected:
            return
        self.bgcolor = (
            colors.bg_surface_hovered if e.data == "true" else colors.bg_surface
        )
        self.update()
