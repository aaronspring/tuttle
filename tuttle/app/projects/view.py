from typing import Callable, Optional

from enum import Enum

from flet import (
    ButtonStyle,
    Card,
    Column,
    Container,
    ElevatedButton,
    FontWeight,
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

from ..clients.view import ClientViewPopUp
from ..core import utils, views
from ..core.abstractions import TView, TViewParams
from ..core.intent_result import IntentResult
from ..projects.intent import ProjectsIntent
from ..res import colors, dimens, fonts, res_utils

from ...model import Contract, Project


def _project_initials(title: str) -> str:
    """Extract up to 2 initials from a project title."""
    parts = (title or "").split()
    return "".join(p[0].upper() for p in parts[:2]) if parts else "?"


class ProjectCard(Container):
    """Flat, bordered card for a project — VS Code panel style."""

    def __init__(
        self, project, on_view_details_clicked, on_delete_clicked, on_edit_clicked
    ):
        self.project: Project = project
        self.on_view_details_clicked = on_view_details_clicked
        self.on_delete_clicked = on_delete_clicked
        self.on_edit_clicked = on_edit_clicked

        _contract_title = "Unknown contract"
        if project.contract:
            _contract_title = project.contract.title
        _client_title = "Unknown client"
        if project.client:
            _client_title = project.client.name

        initials = _project_initials(project.title)
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
                            utils.truncate_str(project.title, 30),
                            weight=fonts.BOLD_FONT,
                        ),
                        views.TBodyText(
                            project.tag or "",
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
            on_click_view=lambda e: self.on_view_details_clicked(project.id),
            on_click_delete=lambda e: self.on_delete_clicked(project.id),
            on_click_edit=lambda e: self.on_edit_clicked(project.id),
        )

        # Info rows
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

        start_str = (
            project.start_date.strftime("%d/%m/%Y") if project.start_date else ""
        )
        end_str = project.end_date.strftime("%d/%m/%Y") if project.end_date else "-"

        body_items = [
            _info_row("Client", _client_title),
            _info_row("Contract", _contract_title),
            Row(
                spacing=dimens.SPACE_MD,
                controls=[
                    _info_row("Start", start_str),
                    _info_row("End", end_str),
                ],
            ),
        ]

        super().__init__(
            expand=True,
            bgcolor=colors.bg_surface,
            border=Border.all(dimens.CARD_BORDER_WIDTH, colors.border),
            border_radius=dimens.RADIUS_LG,
            padding=Padding.all(dimens.SPACE_MD),
            on_hover=self._on_hover,
            on_click=lambda e: self.on_view_details_clicked(project.id),
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


class ViewProjectScreen(views.EntityDetailScreen):
    """View project screen"""

    entity_name = "project"
    edit_route = res_utils.PROJECT_EDITOR_SCREEN_ROUTE

    def __init__(self, params: TViewParams, project_id: str):
        super().__init__(params, project_id, ProjectsIntent())

    def display_entity_data(self):
        """displays the project data on the screen"""
        p = self.entity
        has_contract = True if p.contract else False
        has_client = True if has_contract and p.contract.client else False

        self.project_title_control.value = p.title
        self.client_control.value = (
            f"Client {p.contract.client.name}" if has_client else "Client not specified"
        )
        self.contract_control.value = (
            f"Contract Title: {p.contract.title}"
            if has_contract
            else "Contract not specified"
        )
        self.project_description_control.value = p.description
        self.project_start_date_control.value = f"Start Date: {p.start_date}"
        self.project_end_date_control.value = f"End Date: {p.end_date}"
        _status = p.get_status(default="")
        if _status:
            self.project_status_control.value = f"Status {_status}"
            self.project_status_control.visible = True
        else:
            self.project_status_control.visible = False
        self.project_tagline_control.value = f"{p.tag}"
        is_project_completed = p.is_completed
        self.toggle_complete_status_btn.icon = (
            Icons.RADIO_BUTTON_CHECKED_OUTLINED
            if is_project_completed
            else Icons.RADIO_BUTTON_UNCHECKED_OUTLINED
        )
        self.toggle_complete_status_btn.tooltip = (
            "Mark as incomplete" if is_project_completed else "Mark as complete"
        )

    def on_view_client_clicked(self, e):
        """opens the client view pop up when the client button is clicked"""
        if not self.entity or not self.entity.client:
            return
        if self.popup_handler:
            self.popup_handler.close_dialog()
        self.popup_handler = ClientViewPopUp(
            dialog_controller=self.dialog_controller, client=self.entity.client
        )
        self.popup_handler.open_dialog()

    def on_view_contract_clicked(self, e):
        """redirects to the contract view screen when the contract button is clicked"""
        if not self.entity or not self.entity.contract:
            return
        self.navigate_to_route(
            res_utils.CONTRACT_DETAILS_SCREEN_ROUTE, self.entity.contract.id
        )

    def build(self):
        """Called when page is built"""
        self.edit_project_btn = IconButton(
            icon=Icons.EDIT_OUTLINED,
            tooltip="Edit project",
            on_click=self.on_edit_clicked,
            icon_size=dimens.ICON_SIZE,
        )

        self.toggle_complete_status_btn = IconButton(
            icon=Icons.RADIO_BUTTON_UNCHECKED_OUTLINED,
            icon_color=colors.accent,
            tooltip="Mark as complete",
            icon_size=dimens.ICON_SIZE,
            on_click=self.on_toggle_complete_status,
        )
        self.delete_project_btn = IconButton(
            icon=Icons.DELETE_OUTLINE_ROUNDED,
            icon_color=colors.danger,
            tooltip="Delete project",
            icon_size=dimens.ICON_SIZE,
            on_click=self.on_delete_clicked,
        )

        self.project_title_control = views.THeading()

        self.client_control = views.TSubHeading(color=colors.text_secondary)
        self.contract_control = views.TSubHeading(color=colors.text_secondary)
        self.project_description_control = views.TBodyText(
            align=utils.TXT_ALIGN_JUSTIFY
        )

        self.project_start_date_control = views.TSubHeading(
            size=fonts.BUTTON_SIZE, color=colors.text_secondary
        )
        self.project_end_date_control = views.TSubHeading(
            size=fonts.BUTTON_SIZE, color=colors.text_secondary
        )

        self.project_status_control = views.TSubHeading(
            size=fonts.BUTTON_SIZE, color=colors.accent
        )
        self.project_tagline_control = views.TSubHeading(
            size=fonts.BUTTON_SIZE, color=colors.accent
        )

        page_view = Row(
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
                                tooltip="View project's client",
                                on_click=self.on_view_client_clicked,
                            ),
                            TextButton(
                                "Contract",
                                tooltip="View project's contract",
                                on_click=self.on_view_contract_clicked,
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
                                        Icons.WORK_ROUNDED,
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
                                                        "Project",
                                                        size=fonts.HEADLINE_4_SIZE,
                                                        color=colors.accent,
                                                    ),
                                                    Row(
                                                        vertical_alignment=utils.CENTER_ALIGNMENT,
                                                        alignment=utils.SPACE_BETWEEN_ALIGNMENT,
                                                        spacing=dimens.SPACE_STD,
                                                        run_spacing=dimens.SPACE_STD,
                                                        controls=[
                                                            self.edit_project_btn,
                                                            self.toggle_complete_status_btn,
                                                            self.delete_project_btn,
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            self.project_title_control,
                                            self.client_control,
                                            self.contract_control,
                                        ],
                                    ),
                                ],
                            ),
                            views.Spacer(md_space=True),
                            views.TSubHeading(
                                subtitle="Project Description",
                            ),
                            self.project_description_control,
                            self.project_start_date_control,
                            self.project_end_date_control,
                            views.Spacer(md_space=True),
                            Row(
                                spacing=dimens.SPACE_STD,
                                run_spacing=dimens.SPACE_STD,
                                alignment=utils.START_ALIGNMENT,
                                vertical_alignment=utils.CENTER_ALIGNMENT,
                                controls=[
                                    Card(
                                        Container(
                                            self.project_status_control,
                                            padding=Padding.all(dimens.SPACE_SM),
                                        ),
                                        elevation=2,
                                    ),
                                    Card(
                                        Container(
                                            self.project_tagline_control,
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
        self.content = page_view


class ProjectsListView(views.CrudListView):
    """View for displaying a list of projects"""

    entity_name = "project"
    entity_name_plural = "projects"

    def __init__(self, params):
        self.intent = ProjectsIntent()
        super().__init__(params)

    def make_card(self, project):
        return ProjectCard(
            project=project,
            on_view_details_clicked=lambda pid: self.navigate_to_route(
                res_utils.PROJECT_DETAILS_SCREEN_ROUTE, pid
            ),
            on_delete_clicked=self._on_delete_by_id,
            on_edit_clicked=lambda pid: self.navigate_to_route(
                res_utils.PROJECT_EDITOR_SCREEN_ROUTE, pid
            ),
        )

    def _on_delete_by_id(self, project_id):
        if project_id in self.items_to_display:
            self.on_delete_clicked(self.items_to_display[project_id])

    def get_entity_description(self, project):
        return project.title

    def get_filters_view(self):
        return views.EntityFiltersView(on_state_changed=self.on_filter_changed)


class ProjectEditorScreen(TView, Container):
    """Displays a form for creating or updating a project"""

    def __init__(
        self,
        params: TViewParams,
        project_id_if_editing: Optional[str] = None,
    ):
        super().__init__(params)
        self.horizontal_alignment_in_parent = utils.CENTER_ALIGNMENT
        self.intent = ProjectsIntent()
        self.project_id_if_editing = project_id_if_editing
        self.old_project_if_editing: Optional[Project] = None
        self.contracts_map = {}
        self.loading_indicator = views.TProgressBar()
        self.contract: Optional[Contract] = None
        self.start_date = None
        self.end_date = None

    def make_dropdown_item_unique(self, id, value):
        """Prefixes the dropdown item with an id to make it unique"""
        return f"{id}. {value}"

    def get_id_from_dropdown_selection(self, selected: str):
        """given a dropdown selection, extracts the id from the selection"""
        _id = ""
        for c in selected:
            if c == ".":
                break
            _id = _id + c
        return _id

    def get_contracts_as_list(self):
        """transforms a map of id - to  - contract to a list for dropdown options"""
        contracts = []
        for contract_id in self.contracts_map:
            contracts.append(
                self.make_dropdown_item_unique(
                    id=contract_id, value=self.contracts_map[contract_id].title
                )
            )
        return contracts

    def on_contract_selected(self, e):
        """Called when a contract is selected from the dropdown"""
        contract_id = self.get_id_from_dropdown_selection(selected=e.control.value)
        if int(contract_id) in self.contracts_map:
            self.contract = self.contracts_map[int(contract_id)]
        self.contracts_field.update_error_txt()
        self.update_self()

    def clear_title_error(self, e):
        """Called when the title input is focused"""
        if self.title_field.error:
            self.title_field.error = None
            self.update_self()

    def clear_description_error(self, e):
        """Called when the description input is focused"""
        if self.description_field.error:
            self.description_field.error = None
            self.update_self()

    def toggle_progress_indicator(self, is_action_ongoing: bool):
        """Toggles the progress indicator visibility and disables / enables the submit button"""
        self.loading_indicator.visible = is_action_ongoing
        self.submit_btn.disabled = is_action_ongoing

    def load_project_for_editing(self):
        """Loads the project being edited if a project id was passed to the view"""
        if not self.project_id_if_editing:
            return  # user is not updating a project

        result = self.intent.get_by_id(self.project_id_if_editing)
        if not result.was_intent_successful or not result.data:
            self.show_snack(result.error_msg)
            return  # error loading project
        self.old_project_if_editing = result.data
        self.set_form_values()  # set form values

    def set_form_values(self):
        """Sets form data with info of project being edited"""
        self.title_field.value = self.old_project_if_editing.title
        self.description_field.value = self.old_project_if_editing.description
        self.start_date = self.old_project_if_editing.start_date
        self.start_date_field.set_date(self.start_date)
        self.end_date = self.old_project_if_editing.end_date
        self.end_date_field.set_date(self.end_date)
        self.tag_field.value = self.old_project_if_editing.tag
        self.contract = self.old_project_if_editing.contract
        if self.contract:
            contract_as_list_item = self.make_dropdown_item_unique(
                id=self.contract.id, value=self.contract.title
            )
            self.contracts_field.update_value(contract_as_list_item)
        self.form_title.value = "Edit Project"
        self.submit_btn.text = "Update Project"

    def reload_contracts(
        self,
    ):
        """Reloads the contracts for the dropdown field"""
        self.contracts_map = self.intent.get_all_contracts_as_map()
        self.contracts_field.update_error_txt(
            "Please create a new contract" if len(self.contracts_map) == 0 else ""
        )
        self.contracts_field.update_dropdown_items(self.get_contracts_as_list())

    def on_add_contract(self, e):
        """Called when the add contract button is clicked, redirects to the contract editor screen"""
        self.navigate_to_route(res_utils.CONTRACT_EDITOR_SCREEN_ROUTE)

    def on_save(self, e):
        """Called when the save button is clicked, validates the form and saves the project"""
        if not self.title_field.value:
            self.title_field.error = "Project title is required"
            self.update_self()
            return

        if not self.description_field.value:
            self.description_field.error = "Project description is required"
            self.update_self()
            return

        self.start_date = self.start_date_field.get_date()
        if self.start_date is None:
            self.show_snack("Please specify the start date", True)
            return

        self.end_date = self.end_date_field.get_date()
        if self.end_date is None:
            self.show_snack("Please specify the end date", True)
            return

        if self.start_date > self.end_date:
            self.show_snack(
                "The end date of the project cannot be before the start date", True
            )
            return

        if self.contract is None:
            self.contracts_field.update_error_txt("Please specify the contract")
            self.update_self()
            return

        if not self.tag_field.value:
            self.tag_field.error = "The project must have a tag."
            self.update_self()
            return

        self.toggle_progress_indicator(is_action_ongoing=True)

        project = self.old_project_if_editing or Project()
        project.title = self.title_field.value
        project.description = self.description_field.value
        project.start_date = self.start_date
        project.end_date = self.end_date
        project.tag = self.tag_field.value
        project.contract = self.contract

        result: IntentResult = self.intent.save_project(project)
        successMsg = (
            "Changes saved"
            if self.old_project_if_editing
            else "New project created successfully"
        )
        msg = successMsg if result.was_intent_successful else result.error_msg
        isError = not result.was_intent_successful
        self.toggle_progress_indicator(is_action_ongoing=False)
        self.show_snack(msg, isError)
        if result.was_intent_successful:
            # re -route back
            self.navigate_back()

    def build(self):
        """Builds the view"""
        self.title_field = views.TTextField(
            label="Title",
            hint="A short, unique title",
            on_focus=self.clear_title_error,
        )
        self.description_field = views.TMultilineField(
            label="Description",
            hint="A longer description of the project",
            on_focus=self.clear_description_error,
        )
        self.tag_field = views.TTextField(
            label="Tag",
            hint="A unique tag",
        )

        self.contracts_field = views.TDropDown(
            label="Contract",
            on_change=self.on_contract_selected,
            items=self.get_contracts_as_list(),
        )
        self.start_date_field = views.DateSelector(label="Start Date")
        self.end_date_field = views.DateSelector(label="End Date")
        self.contract_editor = Row(
            alignment=utils.SPACE_BETWEEN_ALIGNMENT,
            vertical_alignment=utils.CENTER_ALIGNMENT,
            spacing=dimens.SPACE_STD,
            controls=[
                self.contracts_field,
                IconButton(
                    icon=Icons.ADD_CIRCLE_OUTLINE,
                    on_click=self.on_add_contract,
                    icon_size=dimens.ICON_SIZE,
                ),
            ],
        )

        self.form_title = views.THeading(
            title="New Project",
        )
        self.submit_btn = views.TPrimaryButton(
            label="Create Project",
            on_click=self.on_save,
        )
        self.content = views.TFullScreenFormContainer(
            form_controls=[
                Row(
                    controls=[
                        views.TBackButton(
                            on_click=self.navigate_back,
                        ),
                        self.form_title,
                    ]
                ),
                self.loading_indicator,
                views.Spacer(md_space=True),
                self.title_field,
                views.Spacer(),
                self.description_field,
                views.Spacer(),
                self.contract_editor,
                views.Spacer(),
                self.tag_field,
                views.Spacer(lg_space=True),
                self.start_date_field,
                views.Spacer(lg_space=True),
                self.end_date_field,
                views.Spacer(lg_space=True),
                self.submit_btn,
            ],
        )

    def did_mount(self):
        """Called when the view is mounted"""
        self.mounted = True
        self.initialize_data()

    def on_resume_after_back_pressed(self):
        """Called when the view is resumed from another screen by back press"""
        self.initialize_data(skip_project_reload=True)

    def initialize_data(self, skip_project_reload: bool = False):
        """Initializes the data for the view"""
        self.toggle_progress_indicator(is_action_ongoing=True)
        if not skip_project_reload:
            self.load_project_for_editing()
        self.reload_contracts()
        self.toggle_progress_indicator(is_action_ongoing=False)
        self.update_self()

    def will_unmount(self):
        """Called when the view is unmounted"""
        self.mounted = False
