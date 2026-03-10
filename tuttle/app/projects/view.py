from typing import Callable, Optional

import datetime
from enum import Enum

from flet import (
    ButtonStyle,
    Card,
    ClipBehavior,
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
    TextOverflow,
    Control,
    Alignment,
    Border,
    BorderSide,
    Icons,
    Padding,
    MainAxisAlignment,
    CrossAxisAlignment,
)

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


class ProjectRow(Container):
    """Single-line list row for a project — macOS native table style."""

    def __init__(
        self, project, on_click, on_delete_clicked, on_edit_clicked, is_selected=False
    ):
        self.project: Project = project

        _contract_title = project.contract.title if project.contract else "—"
        _client_title = project.client.name if project.client else "—"

        _status = project.get_status()
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

        start_str = (
            project.start_date.strftime("%d/%m/%Y") if project.start_date else ""
        )
        end_str = project.end_date.strftime("%d/%m/%Y") if project.end_date else ""
        date_str = f"{start_str} → {end_str}" if start_str else "—"

        _bg = colors.accent_muted if is_selected else colors.bg

        super().__init__(
            bgcolor=_bg,
            border=Border(bottom=BorderSide(1, colors.border)),
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_MD, vertical=dimens.SPACE_SM
            ),
            on_click=lambda e: on_click(project.id),
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
                                    project.title or "",
                                    size=fonts.BODY_1_SIZE,
                                    color=colors.text_primary,
                                    weight=fonts.BOLD_FONT if is_selected else None,
                                    overflow=TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                    expand=True,
                                ),
                            ],
                        ),
                    ),
                    Container(
                        width=200,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            _client_title,
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_secondary,
                            overflow=TextOverflow.ELLIPSIS,
                            max_lines=1,
                        ),
                    ),
                    Container(
                        width=200,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            _contract_title,
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_secondary,
                            overflow=TextOverflow.ELLIPSIS,
                            max_lines=1,
                        ),
                    ),
                    Container(
                        width=180,
                        clip_behavior=ClipBehavior.HARD_EDGE,
                        content=Text(
                            date_str,
                            size=fonts.BODY_2_SIZE,
                            color=colors.text_muted,
                            overflow=TextOverflow.ELLIPSIS,
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


class ProjectSidePanel(views.EntitySidePanel):
    """Right-side panel for viewing and editing projects."""

    def __init__(
        self,
        on_close,
        on_save,
        on_delete,
        intent: ProjectsIntent,
        on_edit_requested=None,
    ):
        self.intent = intent
        self._contracts_map: dict = {}
        self._contract: Optional[Contract] = None
        self._start_date = None
        self._end_date = None
        super().__init__(
            on_close=on_close,
            on_save=on_save,
            on_delete=on_delete,
            on_edit_requested=on_edit_requested,
        )

    def _load_contracts(self):
        self._contracts_map = self.intent.get_all_contracts_as_map()

    def _make_dropdown_item(self, cid, title):
        return f"{cid}. {title}"

    def _get_contract_options(self):
        return [
            self._make_dropdown_item(cid, c.title)
            for cid, c in self._contracts_map.items()
        ]

    # -- Detail view ----------------------------------------------------------

    def build_detail_content(self, entity: Project) -> list:
        p = entity
        _status = p.get_status(default="")
        _status_color = {
            "Active": colors.status_active,
            "Upcoming": colors.status_upcoming,
            "Completed": colors.status_completed,
        }.get(_status, colors.text_muted)

        controls = []

        # Status badge
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

        # Tag
        if p.tag:
            controls.append(
                Text(
                    p.tag,
                    size=fonts.BODY_2_SIZE,
                    color=colors.accent,
                    weight=fonts.BOLD_FONT,
                )
            )

        controls.append(self._get_section_divider())

        # Info fields
        client_name = p.client.name if p.client else "Not specified"
        contract_title = p.contract.title if p.contract else "Not specified"
        controls.append(
            self._get_detail_field("Client", client_name, Icons.PERSON_OUTLINE)
        )
        controls.append(
            self._get_detail_field(
                "Contract", contract_title, Icons.DESCRIPTION_OUTLINED
            )
        )
        controls.append(self._get_detail_field("Description", p.description or ""))
        start = p.start_date.strftime("%d %b %Y") if p.start_date else "—"
        end = p.end_date.strftime("%d %b %Y") if p.end_date else "—"
        controls.append(
            self._get_detail_field("Duration", f"{start}  →  {end}", Icons.DATE_RANGE)
        )

        controls.append(self._get_section_divider())

        # Action buttons
        controls.append(
            self._get_action_bar(
                views.TPrimaryButton(
                    label="Edit",
                    on_click=lambda e: self._switch_to_edit(),
                    icon=Icons.EDIT_OUTLINED,
                ),
                TextButton(
                    content=Text(
                        "Delete",
                        color=colors.danger,
                        size=fonts.BODY_2_SIZE,
                    ),
                    on_click=lambda e: self._on_delete_cb(entity)
                    if self._on_delete_cb
                    else None,
                ),
            )
        )
        return controls

    def build_compact_detail(self, entity: Project) -> list:
        p = entity
        _status = p.get_status(default="")
        _status_color = {
            "Active": colors.status_active,
            "Upcoming": colors.status_upcoming,
            "Completed": colors.status_completed,
        }.get(_status, colors.text_muted)

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
        if p.tag:
            top_row.append(
                Text(
                    p.tag,
                    size=fonts.BODY_2_SIZE,
                    color=colors.accent,
                    weight=fonts.BOLD_FONT,
                )
            )

        detail_fields = []
        if p.description:
            detail_fields.append(
                self._compact_field("Description", p.description, col={"xs": 12}),
            )

        controls = []
        if top_row:
            controls.append(Row(spacing=dimens.SPACE_SM, controls=top_row))
        if detail_fields:
            controls.append(ResponsiveRow(controls=detail_fields))
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
            ),
        )
        return controls

    # -- Edit view ------------------------------------------------------------

    def build_edit_content(self, entity: Optional[Project]) -> list:
        self._load_contracts()
        is_new = entity is None

        self._title_field = views.TTextField(
            label="Title",
            hint="A short, unique title",
            initial_value=entity.title if entity else "",
        )
        self._description_field = views.TMultilineField(
            label="Description",
            hint="A longer description",
            minLines=2,
            maxLines=3,
        )
        if entity and entity.description:
            self._description_field.value = entity.description
        self._tag_field = views.TTextField(
            label="Tag",
            hint="#my-project",
            initial_value=entity.tag if entity else "",
        )

        # Contract dropdown
        self._contract = entity.contract if entity else None
        contract_value = None
        if self._contract:
            contract_value = self._make_dropdown_item(
                self._contract.id, self._contract.title
            )
        self._contracts_field = views.TDropDown(
            label="Contract",
            on_change=self._on_contract_selected,
            items=self._get_contract_options(),
        )
        if contract_value:
            self._contracts_field.update_value(contract_value)

        # Dates
        self._start_date = entity.start_date if entity else None
        self._end_date = entity.end_date if entity else None
        self._start_date_field = views.DateSelector(label="Start Date")
        self._end_date_field = views.DateSelector(label="End Date")
        if self._start_date:
            self._start_date_field.set_date(self._start_date)
        if self._end_date:
            self._end_date_field.set_date(self._end_date)

        save_label = "Create Project" if is_new else "Save Changes"

        # -- Compact multi-column layout --
        self._title_field.col = {"xs": 12, "sm": 8}
        self._tag_field.col = {"xs": 12, "sm": 4}
        self._contracts_field.col = {"xs": 12, "sm": 6}
        self._start_date_field.col = {"xs": 6, "sm": 3}
        self._end_date_field.col = {"xs": 6, "sm": 3}
        self._description_field.col = {"xs": 12}

        return [
            ResponsiveRow(
                controls=[self._title_field, self._tag_field],
                spacing=dimens.SPACE_SM,
            ),
            ResponsiveRow(
                controls=[
                    self._contracts_field,
                    self._start_date_field,
                    self._end_date_field,
                ],
                spacing=dimens.SPACE_SM,
            ),
            ResponsiveRow(
                controls=[self._description_field],
            ),
            self._edit_action_bar(
                save_label,
                on_save=lambda e: self._on_save_clicked(),
                on_cancel=lambda e: self.close(),
            ),
        ]

    def _on_contract_selected(self, e):
        sel = e.control.value
        cid_str = sel.split(".")[0]
        cid = int(cid_str)
        if cid in self._contracts_map:
            self._contract = self._contracts_map[cid]

    def _on_save_clicked(self):
        """Validate and save."""
        if not self._title_field.value:
            self._title_field.error = "Title is required"
            self.update()
            return
        if not self._description_field.value:
            self._description_field.error = "Description is required"
            self.update()
            return

        start = self._start_date_field.get_date()
        end = self._end_date_field.get_date()
        if not start or not end:
            return
        if start > end:
            return
        if not self._contract:
            self._contracts_field.update_error_txt("Contract is required")
            self.update()
            return
        if not self._tag_field.value:
            self._tag_field.error = "Tag is required"
            self.update()
            return

        project = self._entity or Project()
        project.title = self._title_field.value
        project.description = self._description_field.value
        project.start_date = start
        project.end_date = end
        project.tag = self._tag_field.value
        project.contract = self._contract

        if self._on_save_cb:
            self._on_save_cb(project)


class ProjectsListView(views.CrudListView):
    """View for displaying a list of projects"""

    entity_name = "project"
    entity_name_plural = "projects"

    def get_sortable_fields(self):
        return [
            ("Title", lambda p: (p.title or "").lower()),
            (
                "Start Date",
                lambda p: p.start_date if p.start_date else datetime.date.min,
            ),
            ("End Date", lambda p: p.end_date if p.end_date else datetime.date.min),
        ]

    def __init__(self, params):
        self.intent = ProjectsIntent()
        super().__init__(params)

    def get_side_panel(self):
        return ProjectSidePanel(
            on_close=self._on_panel_closed,
            on_save=self._on_project_saved,
            on_delete=self.on_delete_clicked,
            intent=self.intent,
            on_edit_requested=self._on_inline_edit_requested,
        )

    def _on_project_saved(self, project):
        """Save project via intent, close panel, refresh list."""
        result = self.intent.save_project(project)
        if result.was_intent_successful:
            self.show_snack("Project saved!")
            self._side_panel.close()
            self.reload_all_data()
        else:
            self.show_snack(result.error_msg, is_error=True)

    def get_column_headers(self):
        return [
            ("Project", None),
            ("Client", 200),
            ("Contract", 200),
            ("Dates", 180),
        ]

    def make_card(self, project):
        is_selected = self._selected_entity_id == project.id
        return ProjectRow(
            project=project,
            on_click=lambda pid: self._open_detail(pid),
            on_delete_clicked=self._on_delete_by_id,
            on_edit_clicked=lambda pid: self._open_editor(pid),
            is_selected=is_selected,
        )

    def _open_detail(self, project_id):
        if project_id in self.items_to_display:
            self.open_detail_panel(self.items_to_display[project_id])

    def _open_editor(self, project_id):
        if project_id in self.items_to_display:
            self.open_edit_panel(self.items_to_display[project_id])

    def parent_intent_listener(self, intent: str, data=None):
        if intent == res_utils.RELOAD_INTENT:
            self.reload_all_data()
        elif intent == res_utils.PROJECT_EDITOR_SCREEN_ROUTE:
            # "+ New" button opens editor panel for new project
            self.open_edit_panel(None)

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
