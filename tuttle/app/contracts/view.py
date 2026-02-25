from typing import Callable, Optional

from enum import Enum

from flet import (
    Card,
    Column,
    Container,
    Icon,
    IconButton,
    ListTile,
    ResponsiveRow,
    Row,
    Text,
    TextButton,
    Control,
    Alignment,
    Border,
    Icons,
    Padding,
)

from ..clients.view import ClientEditorPopUp, ClientViewPopUp
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


class ContractCard(Container):
    """Flat, bordered card for a contract — VS Code panel style."""

    def __init__(
        self, contract: Contract, on_click_view, on_click_edit, on_click_delete
    ):
        self.contract = contract
        self.on_click_view = on_click_view
        self.on_click_edit = on_click_edit
        self.on_click_delete = on_click_delete

        client_name = contract.client.name if contract.client else "Unknown"
        initials = _contract_initials(contract.title)
        avatar = Container(
            width=36,
            height=36,
            bgcolor=colors.accent_muted,
            border_radius=dimens.RADIUS_LG,
            alignment=Alignment.CENTER,
            content=Text(
                initials,
                size=fonts.BODY_1_SIZE,
                color=colors.accent,
                weight=fonts.BOLD_FONT,
            ),
        )

        header = Row(
            controls=[
                avatar,
                Column(
                    spacing=0,
                    controls=[
                        views.TBodyText(
                            utils.truncate_str(contract.title, 30),
                            weight=fonts.BOLD_FONT,
                        ),
                        views.TBodyText(
                            client_name,
                            color=colors.text_secondary,
                            size=fonts.BODY_2_SIZE,
                        ),
                    ],
                ),
            ],
            spacing=dimens.SPACE_SM,
            expand=True,
            vertical_alignment=utils.CENTER_ALIGNMENT,
        )

        context_menu = views.TContextMenu(
            on_click_view=lambda e: self.on_click_view(contract.id),
            on_click_edit=lambda e: self.on_click_edit(contract.id),
            on_click_delete=lambda e: self.on_click_delete(contract.id),
        )

        def _info_row(label, value):
            return Column(
                spacing=2,
                controls=[
                    views.TBodyText(
                        label, color=colors.text_muted, size=fonts.OVERLINE_SIZE
                    ),
                    views.TBodyText(value, size=fonts.BODY_2_SIZE),
                ],
            )

        body_items = [
            _info_row("Rate", f"{contract.rate} {contract.currency} / {contract.unit}"),
            _info_row("Billing Cycle", f"{contract.billing_cycle}"),
            _info_row("Volume", f"{contract.volume} {contract.unit}s"),
        ]

        super().__init__(
            expand=True,
            bgcolor=colors.bg_surface,
            border=Border.all(dimens.CARD_BORDER_WIDTH, colors.border),
            border_radius=dimens.RADIUS_LG,
            padding=Padding.all(dimens.SPACE_MD),
            on_hover=self._on_hover,
            on_click=lambda e: self.on_click_view(contract.id),
            content=Column(
                spacing=dimens.SPACE_SM,
                controls=[
                    Row(
                        controls=[header, context_menu],
                        alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                        vertical_alignment=utils.START_ALIGNMENT,
                    ),
                    Container(height=1, bgcolor=colors.border_subtle),
                    *body_items,
                ],
            ),
        )

    def _on_hover(self, e):
        self.bgcolor = (
            colors.bg_surface_hovered if e.data == "true" else colors.bg_surface
        )
        self.update()


class ContractEditorScreen(TView, Container):
    """Used to edit or create a contract"""

    def __init__(
        self, params: TViewParams, contract_id_if_editing: Optional[str] = False
    ):
        super().__init__(params=params)
        self.horizontal_alignment_in_parent = utils.CENTER_ALIGNMENT
        self.intent = ContractsIntent()
        self.contract_id_if_editing: Optional[str] = contract_id_if_editing
        self.old_contract_if_editing: Optional[Contract] = None
        self.loading_indicator = views.TProgressBar()
        self.new_client_pop_up: Optional[DialogHandler] = None

        # info of contract being edited / created
        self.clients_map = {}
        self.contacts_map = {}
        self.available_currencies = []
        self.client = None

    def clear_ui_field_errors(self, e):
        """Clears all the errors in the ui form fields"""
        fields = [
            self.title_ui_field,
            self.rate_ui_field,
            self.volume_ui_field,
            self.term_of_payment_ui_field,
            self.unit_PW_ui_field,
            self.vat_rate_ui_field,
        ]
        for field in fields:
            if field.error:
                field.error = None
        self.currency_ui_field.update_error_txt()
        self.update_self()

    def toggle_progress(self, is_on_going_action: bool):
        """Hides or shows the progress bar and enables or disables the submit btn"""
        self.loading_indicator.visible = is_on_going_action
        self.submit_btn.disabled = is_on_going_action

    def did_mount(self):
        """Called when the view is mounted"""
        self.mounted = True
        self.toggle_progress(is_on_going_action=True)
        self.load_clients()
        self.fetch_and_set_contacts()
        self.load_currencies()
        # contract_for_update should be loaded last
        self.load_contract_for_update()
        self.toggle_progress(is_on_going_action=False)
        self.update_self()

    def load_contract_for_update(self):
        """Loads the contract for update if it is an update operation i.e self.contract_id_if_editing is not None"""
        if not self.contract_id_if_editing:
            return  # a new contract is being created
        result = self.intent.get_by_id(self.contract_id_if_editing)
        if not result.was_intent_successful or not result.data:
            self.show_snack(result.error_msg, is_error=True)
        self.old_contract_if_editing = result.data
        self.display_contract_info()

    def load_currencies(self):
        """Loads the available currencies into a dropdown"""
        self.available_currencies = [
            abbreviation for (name, abbreviation, symbol) in utils.get_currencies()
        ]
        self.currency_ui_field.update_dropdown_items(self.available_currencies)
        result = self.intent.get_preferred_currency_intent(self.client_storage)
        if result.was_intent_successful:
            preferred_currency = result.data
            self.currency_ui_field.update_value(preferred_currency)

    def load_clients(self):
        """Loads the clients into a dropdown"""
        self.clients_map = self.intent.get_all_clients_as_map()
        self.clients_ui_field.update_error_txt(
            "Please create a new client" if len(self.clients_map) == 0 else ""
        )
        self.clients_ui_field.update_dropdown_items(self.get_clients_names_as_list())

    def fetch_and_set_contacts(self):
        """fetches the contacts and sets them in the contacts map"""
        self.contacts_map = self.intent.get_all_contacts_as_map()

    def get_clients_names_as_list(self):
        """transforms a map of id-client_title to a list for dropdown options"""
        client_names_list = []
        for key in self.clients_map:
            client_names_list.append(self.get_client_dropdown_item(key))
        return client_names_list

    def get_client_dropdown_item(self, client_id):
        """returns a string for the client's dropdown item"""
        if client_id not in self.clients_map:
            return ""
        # prefix client name with a key {client_id}
        return f"{client_id}. {self.clients_map[client_id].name}"

    def on_client_selected(self, e):
        # parse selected value to extract id
        selected = e.control.value
        _id = ""
        for c in selected:
            if c == ".":
                break
            _id = _id + c

        # clear the error text if any
        self.clients_ui_field.update_error_txt()
        self.update_self()
        if int(_id) in self.clients_map:
            # set the client
            self.client = self.clients_map[int(_id)]

    def on_add_client_clicked(self, e):
        """Called when the add client button is clicked"""
        if self.new_client_pop_up:
            self.new_client_pop_up.close_dialog()
        # open the client editor pop up
        self.new_client_pop_up = ClientEditorPopUp(
            dialog_controller=self.dialog_controller,
            on_submit=self.on_client_set_from_pop_up,
            contacts_map=self.contacts_map,
            on_error=lambda error: self.show_snack(
                error,
                is_error=True,
            ),
        )
        self.new_client_pop_up.open_dialog()

    def on_client_set_from_pop_up(self, client):
        """Called when the client is set from the client editor pop up"""
        if client:
            result: IntentResult = self.intent.save_client(client)
            if result.was_intent_successful:
                self.client: Client = result.data
                self.clients_map[self.client.id] = self.client

                self.clients_ui_field.update_dropdown_items(
                    self.get_clients_names_as_list()
                )

                item = self.get_client_dropdown_item(self.client.id)
                self.clients_ui_field.update_value(item)
                self.clients_ui_field.update_error_txt()
            else:
                self.show_snack(result.error_msg, True)
            self.update_self()

    def display_contract_info(self):
        """initialize form fields with data from old contract"""
        self.title_ui_field.value = self.old_contract_if_editing.title
        signature_date = self.old_contract_if_editing.signature_date
        self.signature_date_ui_field.set_date(signature_date)
        start_date = self.old_contract_if_editing.start_date
        self.start_date_ui_field.set_date(start_date)
        end_date = self.old_contract_if_editing.end_date
        self.end_date_ui_field.set_date(end_date)
        self.client = self.old_contract_if_editing.client
        if self.client:
            self.clients_ui_field.update_value(
                self.get_client_dropdown_item(self.client.id)
            )
        self.rate_ui_field.value = self.old_contract_if_editing.rate
        self.currency_ui_field.update_value(self.old_contract_if_editing.currency)
        self.vat_rate_ui_field.value = self.old_contract_if_editing.VAT_rate
        if self.old_contract_if_editing.unit:
            self.time_unit_field.update_value(self.old_contract_if_editing.unit.name)
        self.unit_PW_ui_field.value = self.old_contract_if_editing.units_per_workday
        self.volume_ui_field.value = self.old_contract_if_editing.volume
        self.term_of_payment_ui_field.value = (
            self.old_contract_if_editing.term_of_payment
        )
        if self.old_contract_if_editing.billing_cycle:
            self.billing_cycle_ui_field.update_value(
                self.old_contract_if_editing.billing_cycle.name
            )
        self.form_title_ui_field.value = "Edit Contract"
        self.submit_btn.text = "Save changes"

    def on_save(self, e):
        """Called when the edit / save button is clicked"""
        # get data from form fields
        title = self.title_ui_field.value
        rate = self.rate_ui_field.value
        vat_rate = self.vat_rate_ui_field.value
        unit_pw = self.unit_PW_ui_field.value
        volume = self.volume_ui_field.value
        term_of_payment = self.term_of_payment_ui_field.value
        currency = self.currency_ui_field.value
        time_unit_str = self.time_unit_field.value
        try:
            time_unit = TimeUnit[time_unit_str]
        except KeyError:
            time_unit = None

        billing_cycle_str = self.billing_cycle_ui_field.value
        try:
            billing_cycle = Cycle[billing_cycle_str]
        except KeyError:
            billing_cycle = None

        # check for missing fields
        if not title:
            self.title_ui_field.error = "Contract title is required"
            self.update_self()
            return  # error occurred, stop here

        if not currency:
            self.currency_ui_field.update_error_txt("Please specify the currency")
            self.update_self()
            return

        if not rate:
            self.rate_ui_field.error = "Rate of enumeration is required"
            self.update_self()
            return

        if not time_unit:
            self.time_unit_field.update_error_txt("Unit of time tracked is required")
            self.update_self()
            return

        if not unit_pw:
            self.unit_PW_ui_field.error = "Units per workday is required"
            self.update_self()
            return

        if self.client is None:
            self.clients_ui_field.update_error_txt("Please select a client")
            self.update_self()
            return  # error occurred, stop here

        if not billing_cycle:
            self.billing_cycle_ui_field.update_error_txt("Billing cycle is required")
            self.update_self()
            return

        signatureDate = self.signature_date_ui_field.get_date()
        if signatureDate is None:
            self.show_snack("Please specify the signature date", True)
            return  # error occurred, stop here

        startDate = self.start_date_ui_field.get_date()
        if startDate is None:
            self.show_snack("Please specify the start date", True)
            return  # error occurred, stop here

        endDate = self.end_date_ui_field.get_date()
        if endDate is None:
            self.show_snack("Please specify the end date", True)
            return  # error occurred, stop here

        if endDate < startDate:
            self.show_snack(
                "The end date of the contract cannot be before the start date", True
            )
            return  # error occurred, stop here

        vat_rate = self.vat_rate_ui_field.value
        if not vat_rate:
            vat_rate = CONTRACT_DEFAULT_VAT_RATE

        self.toggle_progress(is_on_going_action=True)

        contract = self.old_contract_if_editing or Contract()
        contract.title = title
        contract.signature_date = signatureDate
        contract.start_date = startDate
        contract.end_date = endDate
        contract.client = self.client
        contract.rate = rate
        contract.currency = currency
        contract.VAT_rate = vat_rate
        contract.unit = time_unit
        contract.units_per_workday = unit_pw
        contract.volume = volume
        contract.term_of_payment = term_of_payment
        contract.billing_cycle = billing_cycle

        result: IntentResult = self.intent.save_contract(contract)
        success_msg = (
            "Changes saved"
            if self.contract_id_if_editing
            else "New contract created successfully"
        )
        msg = success_msg if result.was_intent_successful else result.error_msg
        isError = not result.was_intent_successful
        self.toggle_progress(is_on_going_action=False)
        self.show_snack(msg, isError)
        if not isError:
            # re route back
            self.navigate_back()

    def build(self):
        """Build the UI"""
        self.title_ui_field = views.TTextField(
            label="Title",
            hint="Short description of the contract.",
            on_focus=self.clear_ui_field_errors,
        )
        self.rate_ui_field = views.TTextField(
            label="Rate",
            hint="Rate of remuneration",
            on_focus=self.clear_ui_field_errors,
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self.currency_ui_field = views.TDropDown(
            label="Currency",
            hint="Payment currency",
            items=self.available_currencies,
        )
        self.vat_rate_ui_field = views.TTextField(
            label="VAT rate",
            hint=f"VAT rate applied to the contractual rate. default is {CONTRACT_DEFAULT_VAT_RATE}",
            on_focus=self.clear_ui_field_errors,
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self.unit_PW_ui_field = views.TTextField(
            label="Units per workday",
            hint="How many units (e.g. hours) constitute a whole work day?",
            on_focus=self.clear_ui_field_errors,
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self.volume_ui_field = views.TTextField(
            label="Volume (optional)",
            hint="Number of time units agreed on",
            on_focus=self.clear_ui_field_errors,
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self.term_of_payment_ui_field = views.TTextField(
            label="Term of payment (optional)",
            hint="How many days after receipt of invoice this invoice is due.",
            on_focus=self.clear_ui_field_errors,
            keyboard_type=utils.KEYBOARD_NUMBER,
        )
        self.clients_ui_field = views.TDropDown(
            label="Client",
            on_change=self.on_client_selected,
            items=self.get_clients_names_as_list(),
        )
        self.time_unit_field = views.TDropDown(
            label="Unit of time tracked.",
            items=[str(t) for t in TimeUnit],
        )
        self.billing_cycle_ui_field = views.TDropDown(
            label="Billing Cycle",
            items=[str(c) for c in Cycle],
        )
        self.signature_date_ui_field = views.DateSelector(label="Signed on")
        self.start_date_ui_field = views.DateSelector(label="Valid from")
        self.end_date_ui_field = views.DateSelector(label="Valid until")
        self.submit_btn = views.TPrimaryButton(
            label="Create Contract", on_click=self.on_save
        )
        self.form_title_ui_field = views.THeading(
            title="New Contract",
        )
        self.content = views.TFullScreenFormContainer(
            form_controls=[
                Row(
                    controls=[
                        views.TBackButton(on_click=self.navigate_back),
                        self.form_title_ui_field,
                    ]
                ),
                self.loading_indicator,
                views.Spacer(md_space=True),
                self.title_ui_field,
                views.Spacer(sm_space=True),
                self.currency_ui_field,
                self.rate_ui_field,
                self.term_of_payment_ui_field,
                self.time_unit_field,
                self.unit_PW_ui_field,
                self.vat_rate_ui_field,
                self.volume_ui_field,
                views.Spacer(sm_space=True),
                Row(
                    alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                    vertical_alignment=utils.CENTER_ALIGNMENT,
                    spacing=dimens.SPACE_STD,
                    controls=[
                        self.clients_ui_field,
                        IconButton(
                            icon=Icons.ADD_CIRCLE_OUTLINE,
                            on_click=self.on_add_client_clicked,
                            icon_size=dimens.ICON_SIZE,
                        ),
                    ],
                ),
                views.Spacer(sm_space=True),
                self.billing_cycle_ui_field,
                views.Spacer(sm_space=True),
                self.signature_date_ui_field,
                views.Spacer(sm_space=True),
                self.start_date_ui_field,
                views.Spacer(md_space=True),
                self.end_date_ui_field,
                views.Spacer(md_space=True),
                self.submit_btn,
            ],
        )

    def will_unmount(self):
        """Called when the view is about to be unmounted."""
        self.mounted = True
        if self.new_client_pop_up:
            self.new_client_pop_up.dimiss_open_dialogs()


class ContractsListView(views.CrudListView):
    """View for displaying a list of contracts."""

    entity_name = "contract"
    entity_name_plural = "contracts"

    def __init__(self, params: TViewParams):
        self.intent = ContractsIntent()
        super().__init__(params)

    def make_card(self, contract):
        return ContractCard(
            contract=contract,
            on_click_view=lambda cid: self.navigate_to_route(
                res_utils.CONTRACT_DETAILS_SCREEN_ROUTE, cid
            ),
            on_click_edit=lambda cid: self.navigate_to_route(
                res_utils.CONTRACT_EDITOR_SCREEN_ROUTE, cid
            ),
            on_click_delete=self._on_delete_by_id,
        )

    def _on_delete_by_id(self, contract_id):
        """Wrap delete_clicked to pass entity object from ID."""
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
        """Displays the data for the contract."""
        c = self.entity
        self.contract_title_control.value = c.title
        self.client_control.value = c.client.name if c.client else "Unknown"
        self.start_date_control.value = c.start_date
        self.end_date_control.value = c.end_date
        _status = c.get_status(default="")
        if _status:
            self.status_control.value = f"Status {_status}"
            self.status_control.visible = True
        else:
            self.status_control.visible = False
        self.billing_cycle_control.value = (
            c.billing_cycle.value if c.billing_cycle else ""
        )
        self.rate_control.value = c.rate
        self.currency_control.value = c.currency
        self.vat_rate_control.value = f"{(c.VAT_rate) * 100:.0f} %"
        time_unit = c.unit.value if c.unit else ""
        self.unit_control.value = time_unit
        self.units_per_workday_control.value = f"{c.units_per_workday} {time_unit}"
        self.volume_control.value = f"{c.volume} {time_unit}"
        self.term_of_payment_control.value = f"{c.term_of_payment} days"
        self.signature_date_control.value = c.signature_date
        self.toggle_compete_status_btn.tooltip = (
            "Mark as incomplete" if c.is_completed else "Mark as completed"
        )
        self.toggle_compete_status_btn.icon = (
            Icons.RADIO_BUTTON_CHECKED_OUTLINED
            if c.is_completed
            else Icons.RADIO_BUTTON_UNCHECKED_OUTLINED
        )

    def build(self):
        """Called when page is built"""
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

        self.client_control = views.THeading()
        self.contract_title_control = views.THeading()
        self.billing_cycle_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.rate_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.currency_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.vat_rate_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.unit_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.units_per_workday_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.volume_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.term_of_payment_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)

        self.signature_date_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.start_date_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
        self.end_date_control = views.TBodyText(align=utils.TXT_ALIGN_JUSTIFY)

        self.status_control = views.TBodyText(
            size=fonts.BUTTON_SIZE, color=colors.accent
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
                            self.get_body_element(
                                "Billing Cycle", self.billing_cycle_control
                            ),
                            self.get_body_element("Rate", self.rate_control),
                            self.get_body_element("Currency", self.currency_control),
                            self.get_body_element("Vat Rate", self.vat_rate_control),
                            self.get_body_element("Time Unit", self.unit_control),
                            self.get_body_element(
                                "Units per Workday", self.units_per_workday_control
                            ),
                            self.get_body_element("Volume", self.volume_control),
                            self.get_body_element(
                                "Term of Payment (days)", self.term_of_payment_control
                            ),
                            self.get_body_element(
                                "Signed on Date", self.signature_date_control
                            ),
                            self.get_body_element(
                                "Start Date", self.start_date_control
                            ),
                            self.get_body_element("End Date", self.end_date_control),
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
