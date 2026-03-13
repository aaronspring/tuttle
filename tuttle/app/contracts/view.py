from typing import Callable, Optional

import datetime
from enum import Enum

from flet import (
    Card,
    ClipBehavior,
    Column,
    Container,
    Icon,
    IconButton,
    ListTile,
    MainAxisAlignment,
    CrossAxisAlignment,
    ResponsiveRow,
    Row,
    Text,
    TextButton,
    Control,
    Alignment,
    Border,
    BorderSide,
    Icons,
    Padding,
)

from ..contracts.intent import ContractsIntent
from ..core import utils, views
from ..core.abstractions import DialogHandler, TView, TViewParams
from ..core.intent_result import IntentResult
from ..res import colors, dimens, fonts, res_utils

from ...model import Client, Contract, CONTRACT_DEFAULT_VAT_RATE
from ...time import Cycle, TimeUnit

LABEL_WIDTH = 80


def _contract_initials(title: str) -> str:
    parts = (title or "").split()
    return "".join(p[0].upper() for p in parts[:2]) if parts else "?"


class ContractRow(Container):
    """Single-line list row for a contract — macOS native table style."""

    def __init__(
        self,
        contract: Contract,
        on_click,
        on_click_edit,
        on_click_delete,
        is_selected=False,
    ):
        self.contract = contract

        client_name = contract.client.name if contract.client else "—"

        _status = contract.get_status()
        _dot_color = {
            "Active": colors.status_active,
            "Upcoming": colors.status_upcoming,
            "Completed": colors.status_completed,
        }.get(_status, colors.text_muted)

        status_dot = Container(
            width=8,
            height=8,
            bgcolor=_dot_color,
            border_radius=dimens.RADIUS_PILL,
        )

        rate_str = (
            f"{contract.rate} {contract.currency}/{contract.unit}"
            if contract.rate
            else "—"
        )

        _bg = colors.accent_muted if is_selected else colors.bg

        super().__init__(
            bgcolor=_bg,
            border=Border(bottom=BorderSide(1, colors.border)),
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_MD, vertical=dimens.SPACE_SM
            ),
            on_click=lambda e: on_click(contract.id),
            on_hover=self._on_hover,
            clip_behavior=ClipBehavior.HARD_EDGE,
            content=Row(
                spacing=dimens.SPACE_MD,
                vertical_alignment=utils.CENTER_ALIGNMENT,
                controls=[
                    Container(
                        expand=True,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Row(
                            spacing=dimens.SPACE_XS,
                            vertical_alignment=utils.CENTER_ALIGNMENT,
                            controls=[
                                status_dot,
                                Text(
                                    contract.title or "",
                                    size=fonts.BODY_1_SIZE,
                                    color=colors.text_primary,
                                    weight=fonts.BOLD_FONT if is_selected else None,
                                    overflow="ellipsis",
                                    max_lines=1,
                                    expand=True,
                                ),
                            ],
                        ),
                    ),
                    Container(
                        width=180,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            client_name,
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_secondary,
                            overflow="ellipsis",
                            max_lines=1,
                        ),
                    ),
                    Container(
                        width=160,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            rate_str,
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_secondary,
                            overflow="ellipsis",
                            max_lines=1,
                        ),
                    ),
                    Container(
                        width=120,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            str(contract.billing_cycle)
                            if contract.billing_cycle
                            else "—",
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_muted,
                            overflow="ellipsis",
                            max_lines=1,
                        ),
                    ),
                ],
            ),
        )
        self._is_selected = is_selected

    def _on_hover(self, e):
        if self._is_selected:
            return
        self.bgcolor = colors.bg_surface_hovered if e.data == "true" else colors.bg
        self.update()


# ── Side panel ────────────────────────────────────────────────


class ContractSidePanel(views.EntitySidePanel):
    """Right-side panel for viewing and editing contracts."""

    def __init__(
        self,
        on_close,
        on_save,
        on_delete,
        intent: ContractsIntent,
        client_storage=None,
        on_edit_requested=None,
    ):
        self.intent = intent
        self._clients_map: dict = {}
        self._contacts_map: dict = {}
        self._client: Optional[Client] = None
        self._client_storage = client_storage
        super().__init__(
            on_close=on_close,
            on_save=on_save,
            on_delete=on_delete,
            on_edit_requested=on_edit_requested,
        )

    def _load_data(self):
        self._clients_map = self.intent.get_all_clients_as_map()
        self._contacts_map = self.intent.get_all_contacts_as_map()
        self._currencies = [abbr for (_, abbr, _) in utils.get_currencies()]

    def _client_item(self, cid):
        return f"{cid}. {self._clients_map[cid].name}"

    def _client_options(self):
        return [self._client_item(cid) for cid in self._clients_map]

    # -- Detail view ----------------------------------------------------------

    def build_detail_content(self, entity: Contract) -> list:
        c = entity
        _status = c.get_status(default="")
        _status_color = {
            "Active": colors.status_active,
            "Upcoming": colors.status_upcoming,
            "Completed": colors.status_completed,
        }.get(_status, colors.text_muted)

        controls = []
        if _status:
            controls.append(
                Container(
                    border_radius=dimens.RADIUS_PILL,
                    bgcolor=_status_color,
                    padding=Padding.symmetric(
                        horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XXS
                    ),
                    content=Text(
                        _status,
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_inverse,
                        weight=fonts.BOLD_FONT,
                    ),
                )
            )

        client_name = c.client.name if c.client else "Not specified"
        controls.append(
            self._get_detail_field("Client", client_name, Icons.PERSON_OUTLINE)
        )
        controls.append(self._get_section_divider())

        # Financial details
        rate_str = f"{c.rate} {c.currency}" if c.rate else "—"
        unit_str = c.unit.value if c.unit else ""
        controls.append(self._get_detail_field("Rate", f"{rate_str} / {unit_str}"))
        vat_str = f"{float(c.VAT_rate)*100:.0f}%" if c.VAT_rate is not None else "—"
        controls.append(self._get_detail_field("VAT Rate", vat_str))
        controls.append(
            self._get_detail_field(
                "Billing Cycle", str(c.billing_cycle) if c.billing_cycle else "—"
            )
        )
        vol_str = f"{c.volume} {unit_str}" if c.volume is not None else "—"
        controls.append(self._get_detail_field("Volume", vol_str))
        upw_str = f"{c.units_per_workday} {unit_str}" if c.units_per_workday else "—"
        controls.append(self._get_detail_field("Units / Workday", upw_str))
        top_str = f"{c.term_of_payment} days" if c.term_of_payment else "—"
        controls.append(self._get_detail_field("Term of Payment", top_str))
        controls.append(self._get_section_divider())

        # Dates
        sig = c.signature_date.strftime("%d %b %Y") if c.signature_date else "—"
        start = c.start_date.strftime("%d %b %Y") if c.start_date else "—"
        end = c.end_date.strftime("%d %b %Y") if c.end_date else "—"
        controls.append(self._get_detail_field("Signed", sig, Icons.DRAW))
        controls.append(
            self._get_detail_field("Duration", f"{start}  →  {end}", Icons.DATE_RANGE)
        )
        controls.append(self._get_section_divider())

        # Actions
        controls.append(
            self._get_action_bar(
                views.TPrimaryButton(
                    label="Edit",
                    on_click=lambda e: self._switch_to_edit(),
                    icon=Icons.EDIT_OUTLINED,
                ),
                TextButton(
                    content=Text("Delete", color=colors.danger, size=fonts.BODY_2_SIZE),
                    on_click=lambda e: self._on_delete_cb(entity)
                    if self._on_delete_cb
                    else None,
                ),
            )
        )
        return controls

    def build_compact_detail(self, entity: Contract) -> list:
        c = entity
        _status = c.get_status(default="")
        _status_color = {
            "Active": colors.status_active,
            "Upcoming": colors.status_upcoming,
            "Completed": colors.status_completed,
        }.get(_status, colors.text_muted)

        unit_str = c.unit.value if c.unit else ""
        vat_str = (
            f"{float(c.VAT_rate)*100:.0f}%" if c.VAT_rate is not None else "\u2014"
        )
        vol_str = f"{c.volume} {unit_str}" if c.volume is not None else "\u2014"
        upw_str = (
            f"{c.units_per_workday} {unit_str}" if c.units_per_workday else "\u2014"
        )
        top_str = f"{c.term_of_payment} days" if c.term_of_payment else "\u2014"
        sig = c.signature_date.strftime("%d %b %Y") if c.signature_date else "\u2014"
        start = c.start_date.strftime("%d %b %Y") if c.start_date else "\u2014"
        end = c.end_date.strftime("%d %b %Y") if c.end_date else "\u2014"

        top_row = []
        if _status:
            top_row.append(
                Container(
                    border_radius=dimens.RADIUS_PILL,
                    bgcolor=_status_color,
                    padding=Padding.symmetric(
                        horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XXS
                    ),
                    content=Text(
                        _status,
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_inverse,
                        weight=fonts.BOLD_FONT,
                    ),
                )
            )

        return [
            Row(spacing=dimens.SPACE_SM, controls=top_row)
            if top_row
            else views.Spacer(xs_space=True),
            ResponsiveRow(
                controls=[
                    self._compact_field("VAT", vat_str),
                    self._compact_field("Volume", vol_str),
                    self._compact_field("Units/Workday", upw_str),
                    self._compact_field("Payment Term", top_str),
                ],
            ),
            ResponsiveRow(
                controls=[
                    self._compact_field("Signed", sig),
                    self._compact_field(
                        "Duration", f"{start}  \u2192  {end}", col={"xs": 6}
                    ),
                ],
            ),
            self._get_action_bar(
                views.TPrimaryButton(
                    label="Edit",
                    on_click=lambda e: self._switch_to_edit(),
                    icon=Icons.EDIT_OUTLINED,
                ),
                TextButton(
                    content=Text("Delete", color=colors.danger, size=fonts.BODY_2_SIZE),
                    on_click=lambda e: self._on_delete_cb(entity)
                    if self._on_delete_cb
                    else None,
                ),
            ),
        ]

    # -- Edit view ------------------------------------------------------------

    def build_edit_content(self, entity: Optional[Contract]) -> list:
        self._load_data()
        is_new = entity is None

        self._title_field = views.TTextField(
            label="Title",
            hint="Short description",
            initial_value=entity.title if entity else "",
        )
        self._rate_field = views.TTextField(
            label="Rate",
            hint="Rate",
            initial_value=str(entity.rate) if entity and entity.rate else "",
            keyboard_type=utils.KEYBOARD_NUMBER,
        )

        # Currency dropdown — default derived from operating country
        preferred_currency = None
        r = self.intent.get_default_currency()
        if r.was_intent_successful:
            preferred_currency = r.data
        cur_value = entity.currency if entity else preferred_currency
        self._currency_field = views.TDropDown(
            label="Currency",
            items=self._currencies,
        )
        if cur_value:
            self._currency_field.update_value(cur_value)

        self._vat_field = views.TTextField(
            label="VAT Rate",
            hint=f"Default: {CONTRACT_DEFAULT_VAT_RATE}",
            initial_value=str(entity.VAT_rate)
            if entity and entity.VAT_rate is not None
            else "",
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self._unit_pw_field = views.TTextField(
            label="Units / workday",
            hint="e.g. 8",
            initial_value=str(entity.units_per_workday)
            if entity and entity.units_per_workday
            else "",
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self._volume_field = views.TTextField(
            label="Volume",
            hint="Total units",
            initial_value=str(entity.volume)
            if entity and entity.volume is not None
            else "",
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self._top_field = views.TTextField(
            label="Payment term",
            hint="Days",
            initial_value=str(entity.term_of_payment)
            if entity and entity.term_of_payment
            else "",
            keyboard_type=utils.KEYBOARD_NUMBER,
        )

        # Time unit
        self._time_unit_field = views.TDropDown(
            label="Time unit",
            items=[str(t) for t in TimeUnit],
        )
        if entity and entity.unit:
            self._time_unit_field.update_value(entity.unit.name)

        # Billing cycle
        self._billing_field = views.TDropDown(
            label="Billing cycle",
            items=[str(c) for c in Cycle],
        )
        if entity and entity.billing_cycle:
            self._billing_field.update_value(entity.billing_cycle.name)

        # Client
        self._client = entity.client if entity else None
        self._clients_field = views.TDropDown(
            label="Client",
            on_change=self._on_client_selected,
            items=self._client_options(),
        )
        if self._client and self._client.id in self._clients_map:
            self._clients_field.update_value(self._client_item(self._client.id))

        # Dates
        self._sig_date_field = views.DateSelector(label="Signed on")
        self._start_date_field = views.DateSelector(label="Valid from")
        self._end_date_field = views.DateSelector(label="Valid until")
        if entity:
            if entity.signature_date:
                self._sig_date_field.set_date(entity.signature_date)
            if entity.start_date:
                self._start_date_field.set_date(entity.start_date)
            if entity.end_date:
                self._end_date_field.set_date(entity.end_date)

        save_label = "Create Contract" if is_new else "Save Changes"

        # -- Multi-column layout --
        self._title_field.col = {"xs": 12, "sm": 6}
        self._clients_field.col = {"xs": 12, "sm": 6}
        self._rate_field.col = {"xs": 6, "sm": 4}
        self._currency_field.col = {"xs": 6, "sm": 4}
        self._time_unit_field.col = {"xs": 6, "sm": 4}
        self._billing_field.col = {"xs": 6, "sm": 6}
        self._vat_field.col = {"xs": 6, "sm": 6}
        self._unit_pw_field.col = {"xs": 6, "sm": 6}
        self._volume_field.col = {"xs": 6, "sm": 6}
        self._top_field.col = {"xs": 6, "sm": 6}
        self._sig_date_field.col = {"xs": 12, "sm": 4}
        self._start_date_field.col = {"xs": 6, "sm": 4}
        self._end_date_field.col = {"xs": 6, "sm": 4}

        return [
            ResponsiveRow(
                controls=[self._title_field, self._clients_field],
                spacing=dimens.SPACE_SM,
            ),
            views.SectionLabel("Pricing"),
            ResponsiveRow(
                controls=[
                    self._rate_field,
                    self._currency_field,
                    self._time_unit_field,
                ],
                spacing=dimens.SPACE_SM,
            ),
            ResponsiveRow(
                controls=[
                    self._billing_field,
                    self._vat_field,
                ],
                spacing=dimens.SPACE_SM,
            ),
            ResponsiveRow(
                controls=[
                    self._unit_pw_field,
                    self._volume_field,
                ],
                spacing=dimens.SPACE_SM,
            ),
            ResponsiveRow(
                controls=[self._top_field],
                spacing=dimens.SPACE_SM,
            ),
            views.SectionLabel("Dates"),
            ResponsiveRow(
                controls=[
                    self._sig_date_field,
                    self._start_date_field,
                    self._end_date_field,
                ],
                spacing=dimens.SPACE_SM,
            ),
            self._edit_action_bar(
                save_label,
                on_save=lambda e: self._validate_and_save(),
                on_cancel=lambda e: self.close(),
            ),
        ]

    def _on_client_selected(self, e):
        sel = e.control.value
        cid = int(sel.split(".")[0])
        if cid in self._clients_map:
            self._client = self._clients_map[cid]

    def _validate_and_save(self):
        title = self._title_field.value
        if not title:
            self._title_field.error = "Title is required"
            self.update()
            return
        currency = self._currency_field.value
        if not currency:
            self._currency_field.update_error_txt("Required")
            self.update()
            return
        rate = self._rate_field.value
        if not rate:
            self._rate_field.error = "Rate is required"
            self.update()
            return
        time_unit_str = self._time_unit_field.value
        try:
            time_unit = TimeUnit[time_unit_str]
        except (KeyError, TypeError):
            self._time_unit_field.update_error_txt("Required")
            self.update()
            return
        unit_pw = self._unit_pw_field.value
        if not unit_pw:
            self._unit_pw_field.error = "Required"
            self.update()
            return
        if not self._client:
            self._clients_field.update_error_txt("Required")
            self.update()
            return
        billing_str = self._billing_field.value
        try:
            billing_cycle = Cycle[billing_str]
        except (KeyError, TypeError):
            self._billing_field.update_error_txt("Required")
            self.update()
            return
        sig_date = self._sig_date_field.get_date()
        start_date = self._start_date_field.get_date()
        end_date = self._end_date_field.get_date()
        if not sig_date or not start_date or not end_date:
            self._sig_date_field.set_error(not sig_date)
            self._start_date_field.set_error(not start_date)
            self._end_date_field.set_error(not end_date)
            self.update()
            return
        if end_date < start_date:
            self._end_date_field.set_error(
                True, "'Valid until' must be after 'Valid from'"
            )
            self.update()
            return
        vat_rate = self._vat_field.value or CONTRACT_DEFAULT_VAT_RATE

        contract = self._entity or Contract()
        contract.title = title
        contract.signature_date = sig_date
        contract.start_date = start_date
        contract.end_date = end_date
        contract.client = self._client
        contract.rate = rate
        contract.currency = currency
        contract.VAT_rate = vat_rate
        contract.unit = time_unit
        contract.units_per_workday = unit_pw
        contract.volume = self._volume_field.value or None
        contract.term_of_payment = self._top_field.value or None
        contract.billing_cycle = billing_cycle

        if self._on_save_cb:
            self._on_save_cb(contract)


class ContractsListView(views.CrudListView):
    """View for displaying a list of contracts."""

    entity_name = "contract"
    entity_name_plural = "contracts"

    def get_sortable_fields(self):
        return [
            ("Title", lambda c: (c.title or "").lower()),
            (
                "Start Date",
                lambda c: c.start_date if c.start_date else datetime.date.min,
            ),
            ("End Date", lambda c: c.end_date if c.end_date else datetime.date.min),
            ("Client", lambda c: (c.client.name if c.client else "").lower()),
        ]

    def __init__(self, params: TViewParams):
        self.intent = ContractsIntent()
        super().__init__(params)

    def get_side_panel(self):
        return ContractSidePanel(
            on_close=self._on_panel_closed,
            on_save=self._on_contract_saved,
            on_delete=self.on_delete_clicked,
            intent=self.intent,
            client_storage=self.client_storage,
            on_edit_requested=self._on_inline_edit_requested,
        )

    def _on_contract_saved(self, contract):
        result = self.intent.save_contract(contract)
        if result.was_intent_successful:
            self.show_snack("Contract saved!")
            self._side_panel.close()
            self.reload_all_data()
        else:
            self.show_snack(result.error_msg, is_error=True)

    def get_column_headers(self):
        return [
            ("Contract", None),
            ("Client", 180),
            ("Rate", 160),
            ("Billing", 120),
        ]

    def make_card(self, contract):
        is_selected = self._selected_entity_id == contract.id
        return ContractRow(
            contract=contract,
            on_click=lambda cid: self._open_detail(cid),
            on_click_edit=lambda cid: self._open_editor(cid),
            on_click_delete=self._on_delete_by_id,
            is_selected=is_selected,
        )

    def _open_detail(self, contract_id):
        if contract_id in self.items_to_display:
            self.open_detail_panel(self.items_to_display[contract_id])

    def _open_editor(self, contract_id):
        if contract_id in self.items_to_display:
            self.open_edit_panel(self.items_to_display[contract_id])

    def parent_intent_listener(self, intent: str, data=None):
        if intent == res_utils.RELOAD_INTENT:
            self.reload_all_data()
        elif intent == res_utils.CONTRACT_EDITOR_SCREEN_ROUTE:
            self.open_edit_panel(None)

    def _on_delete_by_id(self, contract_id):
        if contract_id in self.items_to_display:
            self.on_delete_clicked(self.items_to_display[contract_id])

    def get_entity_description(self, contract):
        return contract.title

    def get_filters_view(self):
        return views.EntityFiltersView(on_state_changed=self.on_filter_changed)

    def will_unmount(self):
        super().will_unmount()
        if self.popup_handler:
            self.popup_handler.dimiss_open_dialogs()


class ViewContractScreen(views.EntityDetailScreen):
    """Screen to view the details of a contract."""

    entity_name = "contract"
    edit_route = res_utils.CONTRACT_EDITOR_SCREEN_ROUTE

    def __init__(self, params: TViewParams, contract_id: str):
        super().__init__(params, contract_id, ContractsIntent())

    def display_entity_data(self):
        c = self.entity
        self.contract_title_control.value = c.title
        self.client_control.value = c.client.name if c.client else "Unknown"
        self.update_field_rows(c)
        _status = c.get_status(default="")
        if _status:
            self.status_control.value = f"Status {_status}"
            self.status_control.visible = True
        else:
            self.status_control.visible = False
        self.toggle_compete_status_btn.tooltip = (
            "Mark as incomplete" if c.is_completed else "Mark as completed"
        )
        self.toggle_compete_status_btn.icon = (
            Icons.RADIO_BUTTON_CHECKED_OUTLINED
            if c.is_completed
            else Icons.RADIO_BUTTON_UNCHECKED_OUTLINED
        )

    def build(self):
        self.edit_contract_btn = IconButton(
            icon=Icons.EDIT_OUTLINED,
            tooltip="Edit contract",
            on_click=self.on_edit_clicked,
            icon_size=dimens.ICON_SIZE,
        )
        self.toggle_compete_status_btn = IconButton(
            icon=Icons.RADIO_BUTTON_CHECKED_OUTLINED,
            icon_color=colors.accent,
            icon_size=dimens.ICON_SIZE,
            tooltip="Mark contract as completed",
            on_click=self.on_toggle_complete_status,
        )
        self.delete_contract_btn = IconButton(
            icon=Icons.DELETE_OUTLINE_ROUNDED,
            icon_color=colors.danger,
            tooltip="Delete contract",
            on_click=self.on_delete_clicked,
            icon_size=dimens.ICON_SIZE,
        )

        self.contract_title_control = views.THeading()
        self.client_control = views.THeading()
        self.status_control = views.TBodyText(
            size=fonts.BUTTON_SIZE, color=colors.accent
        )

        _unit = lambda c: c.unit.value if c.unit else ""
        field_rows = self.build_field_rows(
            [
                ("Billing Cycle", "billing_cycle"),
                ("Rate", "rate"),
                ("Currency", "currency"),
                (
                    "VAT Rate",
                    lambda c: f"{float(c.VAT_rate) * 100:.0f} %"
                    if c.VAT_rate is not None
                    else "",
                ),
                ("Time Unit", "unit"),
                ("Units per Workday", lambda c: f"{c.units_per_workday} {_unit(c)}"),
                (
                    "Volume",
                    lambda c: f"{c.volume} {_unit(c)}" if c.volume is not None else "",
                ),
                (
                    "Term of Payment",
                    lambda c: f"{c.term_of_payment} days"
                    if c.term_of_payment is not None
                    else "",
                ),
                ("Signed on Date", "signature_date"),
                ("Start Date", "start_date"),
                ("End Date", "end_date"),
            ]
        )

        self.content = Row(
            [
                Container(
                    padding=Padding.all(dimens.SPACE_STD),
                    width=int(dimens.MIN_WINDOW_WIDTH * 0.3),
                    content=Column(
                        controls=[
                            IconButton(
                                icon=Icons.KEYBOARD_ARROW_LEFT,
                                on_click=self.navigate_back,
                                icon_size=dimens.ICON_SIZE,
                            ),
                            TextButton(
                                "Client",
                                tooltip="View contract's client",
                                on_click=self.on_view_client_clicked,
                            ),
                        ]
                    ),
                ),
                Container(
                    expand=True,
                    padding=Padding.all(dimens.SPACE_MD),
                    content=Column(
                        controls=[
                            self.loading_indicator,
                            Row(
                                controls=[
                                    Icon(
                                        Icons.HANDSHAKE_ROUNDED,
                                        size=dimens.ICON_SIZE,
                                    ),
                                    Column(
                                        expand=True,
                                        spacing=0,
                                        run_spacing=0,
                                        controls=[
                                            Row(
                                                vertical_alignment=utils.CENTER_ALIGNMENT,
                                                alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                                                controls=[
                                                    views.THeading(
                                                        title="Contract",
                                                        size=fonts.HEADLINE_4_SIZE,
                                                        color=colors.accent,
                                                    ),
                                                    Row(
                                                        vertical_alignment=utils.CENTER_ALIGNMENT,
                                                        alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                                                        spacing=dimens.SPACE_STD,
                                                        run_spacing=dimens.SPACE_STD,
                                                        controls=[
                                                            self.edit_contract_btn,
                                                            self.toggle_compete_status_btn,
                                                            self.delete_contract_btn,
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            self.get_body_element(
                                                "Title", self.contract_title_control
                                            ),
                                            self.get_body_element(
                                                "Client", self.client_control
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            views.Spacer(md_space=True),
                            *field_rows,
                            views.Spacer(md_space=True),
                            Row(
                                spacing=dimens.SPACE_STD,
                                run_spacing=dimens.SPACE_STD,
                                alignment=utils.START_ALIGNMENT,
                                vertical_alignment=utils.CENTER_ALIGNMENT,
                                controls=[
                                    Card(
                                        Container(
                                            self.status_control,
                                            padding=Padding.all(dimens.SPACE_SM),
                                        ),
                                        elevation=2,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
            spacing=dimens.SPACE_XS,
            run_spacing=dimens.SPACE_MD,
            alignment=utils.START_ALIGNMENT,
            vertical_alignment=utils.START_ALIGNMENT,
            expand=True,
        )
