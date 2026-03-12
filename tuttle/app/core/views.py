import typing
from typing import Callable, List, Optional, Type, Union
from dataclasses import dataclass
from enum import Enum
import datetime

from flet import (
    Alignment,
    AlertDialog,
    Border,
    BorderRadius,
    BorderSide,
    Column,
    Card,
    CrossAxisAlignment,
    DatePicker,
    FontWeight,
    IconButton,
    Container,
    Dropdown,
    DropdownOption,
    ElevatedButton,
    FilledButton,
    Icon,
    Icons,
    Image,
    ListView,
    MainAxisAlignment,
    Margin,
    Padding,
    PopupMenuButton,
    PopupMenuItem,
    ProgressBar,
    ButtonStyle,
    NavigationRail,
    ResponsiveRow,
    Row,
    Text,
    TextField,
    TextButton,
    TextStyle,
    Control,
    RoundedRectangleBorder,
)

from ..res import colors, dimens, fonts, image_paths

from .abstractions import DialogHandler, TView, TViewParams
from . import utils
from ..res import res_utils


class Spacer(Container):
    """Creates a space between controls.

    Accepts named size flags for convenience, or a direct pixel value
    via ``default_space``.
    """

    _SIZES = {
        "lg": dimens.SPACE_LG,
        "md": dimens.SPACE_MD,
        "sm": dimens.SPACE_SM,
        "xs": dimens.SPACE_XS,
    }

    def __init__(
        self,
        lg_space: bool = False,
        md_space: bool = False,
        sm_space: bool = False,
        xs_space: bool = False,
        default_space: int = dimens.SPACE_STD,
    ):
        size = default_space
        for flag, name in [
            (lg_space, "lg"),
            (md_space, "md"),
            (sm_space, "sm"),
            (xs_space, "xs"),
        ]:
            if flag:
                size = self._SIZES[name]
                break
        super().__init__(height=size, width=size, padding=0, margin=0)


class THeading(Text):
    """Creates a standard heading."""

    def __init__(
        self,
        title: str = "",
        size: int = fonts.SUBTITLE_1_SIZE,
        color: Optional[str] = None,
        align: str = utils.TXT_ALIGN_LEFT,
        show: bool = True,
        expand: bool | int | None = None,
    ):
        """Displays text formatted as a headline"""
        super().__init__(
            title,
            font_family=fonts.HEADLINE_FONT,
            weight=fonts.BOLD_FONT,
            size=size,
            color=color or colors.text_primary,
            text_align=align,
            visible=show,
            expand=expand,
        )


class TSubHeading(Text):
    """Creates a standard subheading."""

    def __init__(
        self,
        subtitle: str = "",
        size: int = fonts.SUBTITLE_2_SIZE,
        color: Optional[str] = None,
        align: str = utils.TXT_ALIGN_LEFT,
        show: bool = True,
        expand: bool | int | None = None,
    ):
        super().__init__(
            subtitle,
            font_family=fonts.HEADLINE_FONT,
            size=size,
            color=color or colors.text_secondary,
            text_align=align,
            visible=show,
            expand=expand,
        )


class THeadingWithSubheading(Column):
    """Creates a standard heading with a subheading."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        alignment_in_container: str = utils.START_ALIGNMENT,
        txt_alignment: str = utils.TXT_ALIGN_LEFT,
        title_size: int = fonts.SUBTITLE_1_SIZE,
        subtitle_size: int = fonts.SUBTITLE_2_SIZE,
        subtitle_color: Optional[str] = None,
    ):
        super().__init__(
            spacing=2,
            horizontal_alignment=alignment_in_container,
            controls=[
                THeading(
                    title=title,
                    size=title_size,
                    align=txt_alignment,
                ),
                TSubHeading(
                    subtitle=subtitle,
                    size=subtitle_size,
                    align=txt_alignment,
                    color=subtitle_color or colors.text_secondary,
                ),
            ],
        )


class TBodyText(Text):
    """Creates a standard body text."""

    def __init__(
        self,
        txt: str = "",
        size: int = fonts.BODY_1_SIZE,
        color: Optional[str] = None,
        show: bool = True,
        col: Optional[dict] = None,
        align: str = utils.TXT_ALIGN_LEFT,
        **kwargs,
    ):
        super().__init__(
            col=col,
            value=txt,
            color=color or colors.text_primary,
            size=size,
            visible=show,
            text_align=align,
            **kwargs,
        )


class TTextField(TextField):
    """Flat text field with filled background — VS Code input style."""

    def __init__(
        self,
        on_change: typing.Optional[Callable] = None,
        label: str = "",
        hint: str = "",
        keyboard_type: str = utils.KEYBOARD_TEXT,
        on_focus: typing.Optional[Callable] = None,
        initial_value: typing.Optional[str] = None,
        expand: typing.Optional[int] = None,
        width: typing.Optional[int] = None,
        show: bool = True,
    ):
        super().__init__(
            label=label,
            keyboard_type=keyboard_type,
            content_padding=Padding.symmetric(
                horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XS
            ),
            hint_text=hint,
            hint_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.text_muted),
            value=initial_value,
            filled=True,
            bgcolor=colors.bg_input,
            focused_bgcolor=colors.bg_input,
            border_color=colors.border,
            focused_border_color=colors.accent,
            focused_border_width=1,
            border_width=1,
            border_radius=dimens.RADIUS_MD,
            color=colors.text_primary,
            cursor_color=colors.accent,
            on_focus=on_focus,
            on_change=on_change,
            password=keyboard_type == utils.KEYBOARD_PASSWORD,
            expand=expand,
            width=width,
            disabled=keyboard_type == utils.KEYBOARD_NONE,
            text_size=fonts.BODY_1_SIZE,
            label_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.text_secondary),
            error_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.danger),
            visible=show,
        )


class TMultilineField(TextField):
    """Flat multiline text field."""

    def __init__(
        self,
        on_change: typing.Optional[Callable] = None,
        label: str = "",
        hint: str = "",
        on_focus: typing.Optional[Callable] = None,
        keyboardType: str = utils.KEYBOARD_MULTILINE,
        minLines: int = 3,
        maxLines: int = 5,
    ):
        super().__init__(
            label=label,
            keyboard_type=keyboardType,
            hint_text=hint,
            hint_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.text_muted),
            filled=True,
            bgcolor=colors.bg_input,
            focused_bgcolor=colors.bg_input,
            border_color=colors.border,
            focused_border_color=colors.accent,
            focused_border_width=1,
            border_width=1,
            border_radius=dimens.RADIUS_MD,
            color=colors.text_primary,
            cursor_color=colors.accent,
            min_lines=minLines,
            max_lines=maxLines,
            on_focus=on_focus,
            on_change=on_change,
            text_size=fonts.BODY_1_SIZE,
            label_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.text_secondary),
            error_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.danger),
        )


class TErrorText(TBodyText):
    """Displays text formatted for errors / warnings."""

    def __init__(self, txt: str, show: bool = True):
        super().__init__(txt, color=colors.danger, show=show)


class TPrimaryButton(FilledButton):
    """Compact primary action button — accent-colored."""

    def __init__(
        self,
        on_click: Optional[Callable] = None,
        label: str = "",
        width: Optional[int] = None,
        icon: Optional[str] = None,
        show: bool = True,
    ):
        super().__init__(
            label,
            on_click=on_click,
            icon=icon,
            visible=show,
            width=width,
            height=dimens.CLICKABLE_STD_HEIGHT,
            style=ButtonStyle(
                bgcolor=colors.accent,
                color=colors.text_inverse,
                shape=RoundedRectangleBorder(radius=dimens.RADIUS_MD),
            ),
        )


class TSecondaryButton(ElevatedButton):
    """Outlined secondary action button."""

    def __init__(
        self,
        on_click: Optional[Callable] = None,
        label: str = "",
        width: Optional[int] = None,
        icon: Optional[str] = None,
    ):
        super().__init__(
            label,
            on_click=on_click,
            icon=icon,
            width=width,
            height=dimens.CLICKABLE_STD_HEIGHT,
            color=colors.text_primary,
            style=ButtonStyle(
                shape=RoundedRectangleBorder(radius=dimens.RADIUS_MD),
                side=BorderSide(width=1, color=colors.border),
                bgcolor=colors.bg_surface,
            ),
        )


class TDangerButton(ElevatedButton):
    """Button styled for dangerous actions (delete, reset)."""

    def __init__(
        self,
        on_click: Optional[Callable] = None,
        label: str = "",
        width: Optional[int] = None,
        icon: Optional[str] = None,
        tooltip: Optional[str] = None,
    ):
        super().__init__(
            content=label,
            color=colors.danger,
            on_click=on_click,
            icon=icon,
            icon_color=colors.danger,
            tooltip=tooltip,
            width=width,
            height=dimens.CLICKABLE_STD_HEIGHT,
            style=ButtonStyle(
                shape=RoundedRectangleBorder(radius=dimens.RADIUS_MD),
                side=BorderSide(width=1, color=colors.danger),
                bgcolor=colors.bg_surface,
            ),
        )


class TProfilePhotoImg(Image):
    """Creates a profile photo image — circular avatar."""

    def __init__(self, pic_src: str = image_paths.default_avatar):
        super().__init__(
            src=pic_src,
            width=64,
            height=64,
            border_radius=BorderRadius.all(32),
            fit=utils.CONTAIN,
        )


class TImage(Container):
    """Image wrapped in a container."""

    def __init__(self, path: str, semantic_label: str, width: int):
        super().__init__(
            width=width,
            content=Image(src=path, fit=utils.CONTAIN, semantics_label=semantic_label),
        )


class TProgressBar(ProgressBar):
    """Thin accent-colored progress bar."""

    def __init__(self, show: bool = True):
        super().__init__(
            width=None,
            height=2,
            visible=show,
            color=colors.accent,
            bgcolor=colors.border_subtle,
        )


class TDropDown(Column):
    """Styled dropdown matching the flat input style."""

    def __init__(
        self,
        label: str,
        on_change: Optional[Callable] = None,
        items: List[str] = [],
        hint: Optional[str] = "",
        width: Optional[int] = None,
        initial_value: Optional[str] = None,
        show: bool = True,
    ):
        super().__init__()
        self.visible = show
        self.label = label
        self.on_change = on_change
        self.initial_value = initial_value
        self.width = width
        self.hint = hint
        self.options = [DropdownOption(text=item) for item in items]
        self.drop_down = Dropdown(
            label=self.label,
            hint_text=self.hint,
            options=self.options,
            text_size=fonts.BODY_1_SIZE,
            label_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.text_secondary),
            on_select=self.on_change,
            width=self.width,
            value=self.initial_value,
            content_padding=Padding.symmetric(
                horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XS
            ),
            error_style=TextStyle(size=fonts.BODY_2_SIZE, color=colors.danger),
            visible=self.visible,
            filled=True,
            bgcolor=colors.bg_input,
            border_color=colors.border,
            focused_border_color=colors.accent,
            border_width=1,
            border_radius=dimens.RADIUS_MD,
            color=colors.text_primary,
        )

    def update_dropdown_items(self, items: List[str]):
        self.options = [DropdownOption(text=item) for item in items]
        self.drop_down.options = self.options
        self.update()

    def update_value(self, new_value: str):
        self.drop_down.value = new_value
        self.drop_down.error_text = None
        try:
            self.update()
        except RuntimeError:
            pass  # control not yet mounted

    @property
    def value(self):
        return self.drop_down.value

    def update_error_txt(self, error_txt: str = ""):
        self.drop_down.error_text = error_txt if error_txt else None
        self.update()

    def build(self):
        self.controls = [self.drop_down]


class DateSelector(Container):
    """Date selector that opens a native Material DatePicker dialog."""

    _DATE_FMT = "%b %d, %Y"

    def __init__(
        self,
        label: str,
        initial_date: Optional[datetime.date] = None,
        label_color: Optional[str] = None,
    ):
        super().__init__()
        self.label = label
        if initial_date is None:
            self._selected_date: Optional[datetime.date] = datetime.date.today()
        elif isinstance(initial_date, datetime.datetime):
            self._selected_date: Optional[datetime.date] = initial_date.date()
        else:
            self._selected_date: Optional[datetime.date] = initial_date
        self.label_color = label_color or colors.text_secondary

        today = datetime.date.today()
        self._picker = DatePicker(
            value=datetime.datetime.combine(self._selected_date, datetime.time()),
            first_date=datetime.datetime(year=today.year - 10, month=1, day=1),
            last_date=datetime.datetime(year=today.year + 10, month=12, day=31),
            help_text=label,
            on_change=self._on_picked,
        )

        display = (
            self._selected_date.strftime(self._DATE_FMT)
            if self._selected_date
            else "Select date"
        )
        display_color = (
            colors.text_primary if self._selected_date else colors.text_muted
        )
        self._date_text = Text(
            value=display,
            size=fonts.BODY_1_SIZE,
            color=display_color,
        )

    def _on_picked(self, e):
        picked = e.control.value
        if picked is not None:
            if isinstance(picked, datetime.datetime):
                self._selected_date = picked.date()
            else:
                self._selected_date = picked
            self._date_text.value = self._selected_date.strftime(self._DATE_FMT)
            self._date_text.color = colors.text_primary
            self.update()

    def _open_picker(self, e):
        if self._selected_date:
            self._picker.value = datetime.datetime.combine(
                self._selected_date, datetime.time()
            )
        self.page.show_dialog(self._picker)

    def build(self):
        self.content = Column(
            spacing=dimens.SPACE_XXS,
            controls=[
                Text(
                    value=self.label,
                    size=fonts.BODY_2_SIZE,
                    color=self.label_color,
                ),
                Container(
                    on_click=self._open_picker,
                    border_radius=dimens.RADIUS_MD,
                    border=Border(
                        top=BorderSide(width=1, color=colors.border),
                        right=BorderSide(width=1, color=colors.border),
                        bottom=BorderSide(width=1, color=colors.border),
                        left=BorderSide(width=1, color=colors.border),
                    ),
                    bgcolor=colors.bg_input,
                    padding=Padding(
                        left=dimens.SPACE_SM,
                        right=dimens.SPACE_XS,
                        top=dimens.SPACE_XS,
                        bottom=dimens.SPACE_XS,
                    ),
                    content=Row(
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                        controls=[
                            self._date_text,
                            Icon(
                                Icons.CALENDAR_MONTH_OUTLINED,
                                size=dimens.ICON_SIZE,
                                color=colors.accent,
                            ),
                        ],
                    ),
                ),
            ],
        )

    def set_date(self, date: Optional[datetime.date] = None):
        if date is None:
            return
        self._selected_date = date
        self._picker.value = datetime.datetime.combine(date, datetime.time())
        self._date_text.value = date.strftime(self._DATE_FMT)
        self._date_text.color = colors.text_primary
        try:
            self.update()
        except RuntimeError:
            pass  # control not yet attached to a page

    def get_date(self) -> Optional[datetime.date]:
        return self._selected_date


class ConfirmDisplayPopUp(DialogHandler):
    """Confirmation dialog with proceed / cancel actions."""

    def __init__(
        self,
        dialog_controller: Callable[[any, utils.AlertDialogControls], None],
        title: str,
        description: str,
        on_proceed: Callable,
        data_on_confirmed: Optional[any] = None,
        on_cancel: Optional[Callable] = None,
        proceed_button_label: str = "Proceed",
        cancel_button_label: str = "Cancel",
    ):
        dialog = AlertDialog(
            bgcolor=colors.bg_surface,
            content=Container(
                height=150,
                content=Column(
                    scroll=utils.AUTO_SCROLL,
                    controls=[
                        THeading(title=title, size=fonts.HEADLINE_4_SIZE),
                        Spacer(xs_space=True),
                        TBodyText(txt=description, size=fonts.BODY_1_SIZE),
                    ],
                ),
            ),
            actions=[
                TSecondaryButton(
                    label=cancel_button_label, on_click=self.on_cancel_btn_clicked
                ),
                TPrimaryButton(
                    label=proceed_button_label, on_click=self.on_proceed_btn_clicked
                ),
            ],
        )
        super().__init__(dialog=dialog, dialog_controller=dialog_controller)
        self.on_proceed_callback = on_proceed
        self.on_cancel_callback = on_cancel
        self.data_on_confirmed = data_on_confirmed

    def on_cancel_btn_clicked(self, e):
        self.close_dialog()
        if self.on_cancel_callback:
            self.on_cancel_callback()

    def on_proceed_btn_clicked(self, e):
        self.close_dialog()
        if self.data_on_confirmed is not None:
            self.on_proceed_callback(self.data_on_confirmed)
        else:
            self.on_proceed_callback()


class TPopUpMenuItem(PopupMenuItem):
    """Styled popup menu item with icon + text."""

    def __init__(self, icon, txt, on_click, is_delete: bool = False):
        item_color = colors.danger if is_delete else colors.text_primary
        super().__init__(
            content=Row(
                [
                    Icon(icon, size=dimens.ICON_SIZE, color=item_color),
                    TBodyText(txt, size=fonts.BODY_1_SIZE, color=item_color),
                ],
                spacing=dimens.SPACE_SM,
            ),
            on_click=on_click,
        )


class TContextMenu(PopupMenuButton):
    """Three-dot context menu with optional view / edit / delete items."""

    def __init__(
        self,
        on_click_edit: Optional[Callable] = None,
        on_click_delete: Optional[Callable] = None,
        view_item_lbl="View Details",
        delete_item_lbl="Delete",
        edit_item_lbl="Edit",
        on_click_view: Optional[Callable] = None,
        prefix_menu_items: Optional[list[PopupMenuItem]] = None,
        suffix_menu_items: Optional[list[PopupMenuItem]] = None,
    ):
        items = []
        if prefix_menu_items:
            items.extend(prefix_menu_items)
        if on_click_view:
            items.append(
                TPopUpMenuItem(
                    Icons.VISIBILITY_OUTLINED, txt=view_item_lbl, on_click=on_click_view
                )
            )
        if on_click_edit:
            items.append(
                TPopUpMenuItem(
                    Icons.EDIT_OUTLINED, txt=edit_item_lbl, on_click=on_click_edit
                )
            )
        if on_click_delete:
            items.append(
                TPopUpMenuItem(
                    Icons.DELETE_OUTLINE,
                    txt=delete_item_lbl,
                    on_click=on_click_delete,
                    is_delete=True,
                )
            )
        if suffix_menu_items:
            items.extend(suffix_menu_items)
        super().__init__(
            items=items,
            icon=Icons.MORE_HORIZ,
            icon_size=dimens.ICON_SIZE,
            icon_color=colors.text_muted,
        )


class TStatusDisplay(Row):
    """Check / uncheck icon + text — for completion status."""

    def __init__(self, txt: str, is_done: bool):
        super().__init__(
            spacing=dimens.SPACE_SM,
            controls=[
                Icon(
                    Icons.CHECK_CIRCLE_OUTLINE
                    if is_done
                    else Icons.RADIO_BUTTON_UNCHECKED,
                    size=dimens.SM_ICON_SIZE,
                    color=colors.success if is_done else colors.text_muted,
                ),
                TBodyText(
                    txt, color=colors.text_primary if is_done else colors.text_secondary
                ),
            ],
        )


class OrView(Row):
    """Visual divider showing '--- OR ---'."""

    def __init__(self, show_lines: Optional[bool] = True, show: bool = True):
        super().__init__(
            visible=show,
            alignment=utils.SPACE_BETWEEN_ALIGNMENT
            if show_lines
            else utils.CENTER_ALIGNMENT,
            vertical_alignment=utils.CENTER_ALIGNMENT,
            controls=[
                Container(
                    height=1, bgcolor=colors.border, width=100, visible=show_lines
                ),
                TBodyText("OR", align=utils.TXT_ALIGN_CENTER, color=colors.text_muted),
                Container(
                    height=1, bgcolor=colors.border, width=100, visible=show_lines
                ),
            ],
        )


@dataclass
class NavigationMenuItem:
    """Defines a menu item used in the navigation system."""

    index: int
    label: str
    icon: str
    selected_icon: str
    destination: Control
    on_new_screen_route: Optional[str] = None
    on_new_intent: Optional[str] = None


class SectionLabel(Container):
    """Uppercase muted section header — macOS sidebar style."""

    def __init__(self, title: str):
        super().__init__(
            padding=Padding.only(
                left=dimens.SPACE_STD, top=dimens.SPACE_LG, bottom=dimens.SPACE_XS
            ),
            content=Text(
                title.upper(),
                size=fonts.CAPTION_SIZE,
                color=colors.text_muted,
                weight=fonts.BOLD_FONT,
                style=TextStyle(letter_spacing=1.2),
            ),
        )


class SidebarNavItem(Container):
    """A single sidebar navigation item — macOS-native feel."""

    # Semi-transparent white tint for selected state (native macOS style)
    _SELECTED_BG = "#14FFFFFF"  # ~8% white
    _HOVER_BG = "#0AFFFFFF"  # ~4% white

    def __init__(
        self,
        label: str,
        icon: str,
        selected_icon: str,
        selected: bool = False,
        on_click: Optional[Callable] = None,
    ):
        self._selected = selected
        self._icon = icon
        self._selected_icon = selected_icon
        self._on_click = on_click

        bg = self._SELECTED_BG if selected else None
        icon_color = colors.text_inverse if selected else colors.text_muted
        text_color = colors.text_primary if selected else colors.text_secondary
        current_icon = selected_icon if selected else icon

        super().__init__(
            bgcolor=bg,
            border_radius=dimens.RADIUS_LG,
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_SM + 2, vertical=dimens.SPACE_XS + 2
            ),
            margin=Margin.symmetric(horizontal=dimens.SPACE_XS, vertical=1),
            on_click=on_click,
            on_hover=self._on_hover,
            content=Row(
                controls=[
                    Icon(current_icon, size=dimens.ICON_SIZE, color=icon_color),
                    Text(
                        label,
                        size=fonts.BODY_1_SIZE,
                        color=text_color,
                        weight=fonts.BOLD_FONT if selected else None,
                    ),
                ],
                spacing=dimens.SPACE_SM,
                vertical_alignment=utils.CENTER_ALIGNMENT,
            ),
        )

    def _on_hover(self, e):
        if not self._selected:
            self.bgcolor = self._HOVER_BG if e.data == "true" else None
            self.update()


class SidebarPanel(Column):
    """VS Code-style sidebar panel with sections and nav items.

    Replaces the old dual ``TNavigationMenuNoLeading`` / ``TNavigationMenu``
    widgets with a flat list layout grouped under section headers.
    """

    def __init__(
        self,
        sections: list[tuple[str, list[NavigationMenuItem]]],
        on_item_selected: Optional[Callable] = None,
        initial_selected_index: int = 0,
    ):
        super().__init__(
            spacing=0,
            expand=True,
        )
        self._sections = sections
        self._on_item_selected = on_item_selected
        self._flat_items: list[NavigationMenuItem] = []
        self._nav_controls: list[SidebarNavItem] = []
        self._selected_index = initial_selected_index

        for _, items in sections:
            self._flat_items.extend(items)
        self._build_controls()

    def _build_controls(self):
        controls = []
        flat_idx = 0
        for section_title, items in self._sections:
            controls.append(SectionLabel(section_title))
            for item in items:
                is_selected = flat_idx == self._selected_index
                nav = SidebarNavItem(
                    label=item.label,
                    icon=item.icon,
                    selected_icon=item.selected_icon,
                    selected=is_selected,
                    on_click=lambda e, idx=flat_idx: self._handle_click(idx),
                )
                self._nav_controls.append(nav)
                controls.append(nav)
                flat_idx += 1
        self.controls = controls

    def _handle_click(self, index: int):
        self._selected_index = index
        # Rebuild all nav items to reflect selection
        self._nav_controls.clear()
        self._build_controls()
        self.update()
        if self._on_item_selected:
            self._on_item_selected(self._flat_items[index])

    @property
    def selected_item(self) -> NavigationMenuItem:
        return self._flat_items[self._selected_index]

    @property
    def selected_index(self) -> int:
        return self._selected_index

    def setBgColor(self, color):
        """Backward-compat: no-op (sidebar bg is set on the container)."""
        pass


# ── Backward-compat aliases ──────────────────────────────────
# Old code that constructs TNavigationMenuNoLeading still works
# but creates a simplified wrapper.


class TNavigationMenu(NavigationRail):
    """DEPRECATED — kept for backward compat. Use SidebarPanel instead."""

    def __init__(
        self,
        title="",
        on_change=None,
        selected_index=0,
        destinations=None,
        menu_height=300,
        width=220,
        left_padding=16,
        top_margin=16,
    ):
        super().__init__(
            selected_index=selected_index,
            min_width=utils.COMPACT_RAIL_WIDTH,
            extended=True,
            height=menu_height,
            min_extended_width=width,
            destinations=destinations or [],
            on_change=on_change,
            bgcolor=colors.bg_sidebar,
        )


class TNavigationMenuNoLeading(Column):
    """DEPRECATED — kept for backward compat. Use SidebarPanel instead."""

    def __init__(
        self,
        title="",
        on_change=None,
        selected_index=0,
        destinations=None,
        menu_height=200,
        width=220,
        left_padding=16,
        top_margin=16,
    ):
        super().__init__()
        self.titleContainer = Container(
            content=TSubHeading(
                subtitle=title,
                align=utils.TXT_ALIGN_LEFT,
                expand=True,
                color=colors.text_muted,
            ),
            expand=False,
            width=width,
            alignment=Alignment.CENTER_LEFT,
            margin=Margin.only(top=top_margin),
            padding=Padding.only(left=left_padding),
        )
        self.navigationRail = NavigationRail(
            selected_index=selected_index,
            min_width=utils.COMPACT_RAIL_WIDTH,
            extended=True,
            height=menu_height,
            min_extended_width=width,
            destinations=destinations or [],
            on_change=on_change,
            bgcolor=colors.bg_sidebar,
        )

    def setBgColor(self, color):
        self.navigationRail.bgcolor = color
        self.titleContainer.bgcolor = color
        if hasattr(self, "page") and self.page is not None:
            self.update()

    def build(self):
        self.alignment = utils.START_ALIGNMENT
        self.horizontal_alignment = utils.START_ALIGNMENT
        self.spacing = 0
        self.run_spacing = 0
        self.controls = [self.titleContainer, self.navigationRail]


class TBackButton(IconButton):
    """Chevron-left back button."""

    def __init__(self, on_click: Optional[Callable] = None):
        return super().__init__(
            icon=Icons.CHEVRON_LEFT_ROUNDED,
            on_click=on_click,
            icon_size=dimens.MD_ICON_SIZE,
            icon_color=colors.text_secondary,
        )


class TFullScreenFormContainer(Container):
    """Centered form container with max-width constraint."""

    def __init__(self, form_controls: list[Control]):
        return super().__init__(
            expand=True,
            padding=Padding.all(dimens.SPACE_LG),
            margin=Margin.symmetric(vertical=dimens.SPACE_MD),
            content=Container(
                expand=True,
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_XL,
                content=Container(
                    Column(expand=True, controls=form_controls),
                    padding=Padding.all(dimens.SPACE_LG),
                    width=720,
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Generic base classes for entity CRUD views
# ---------------------------------------------------------------------------


class EntityStates(Enum):
    """Filter states for entity lists (contracts, projects, etc.)."""

    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"
    UPCOMING = "upcoming"

    def __str__(self):
        return self.name.capitalize()

    @property
    def tooltip(self):
        return {
            EntityStates.ALL: "View all items",
            EntityStates.ACTIVE: "View currently active items",
            EntityStates.COMPLETED: "View completed items",
            EntityStates.UPCOMING: "View upcoming items",
        }.get(self, "")


class EntityFiltersView(Row):
    """Compact text-tab filter bar for entity lists — macOS style."""

    def __init__(self, on_state_changed: Callable, states_enum=EntityStates):
        super().__init__()
        self.states_enum = states_enum
        self.current_state = states_enum.ALL
        self.on_state_changed = on_state_changed

    def on_filter_button_clicked(self, state):
        self.current_state = state
        self._rebuild_chips()
        self.on_state_changed(state)
        self.update()

    def _rebuild_chips(self):
        """Rebuild chip controls into the inner row, like invoicing does."""
        chips = []
        for state in self.states_enum:
            is_active = self.current_state == state
            chips.append(
                Container(
                    on_click=lambda e, s=state: self.on_filter_button_clicked(s),
                    border_radius=dimens.RADIUS_PILL,
                    padding=Padding.symmetric(
                        horizontal=dimens.SPACE_SM,
                        vertical=dimens.SPACE_XXS,
                    ),
                    bgcolor=colors.accent if is_active else colors.bg_input,
                    content=Text(
                        str(state),
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_inverse
                        if is_active
                        else colors.text_secondary,
                        weight=fonts.BOLD_FONT if is_active else None,
                    ),
                    tooltip=state.tooltip,
                )
            )
        self._chip_row.controls = chips

    def build(self):
        self._chip_row = Row(
            controls=[],
            spacing=dimens.SPACE_XXS,
        )
        self._rebuild_chips()
        self.controls = [self._chip_row]


# ---------------------------------------------------------------------------
# EntitySidePanel — unified right-side panel for detail & edit
# ---------------------------------------------------------------------------


class EntitySidePanel(Container):
    """Slide-in right-side panel for viewing and editing entities.

    Modeled after PdfViewerPanel: hidden by default, uses ``visible`` toggle.
    Sits inside a ``Row`` next to the entity grid. When visible the grid
    shrinks and the panel fills the remaining space.

    Subclasses override:
        - ``build_detail_content(entity)`` -> list[Control]
        - ``build_edit_content(entity)``   -> list[Control]
        - ``on_save(entity)``              -> handle save result
    """

    def __init__(
        self,
        on_close: Callable,
        on_save: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        on_edit_requested: Optional[Callable] = None,
    ):
        self._on_close = on_close
        self._on_save_cb = on_save
        self._on_delete_cb = on_delete
        self._on_edit_requested = on_edit_requested
        self._entity = None
        self._mode = "view"  # "view" or "edit"
        # When used as an inline content builder (not mounted in tree),
        # update() calls are routed through this container instead.
        self._inline_container: Optional[Container] = None

        # Header
        self._title_text = THeading(title="", size=fonts.HEADLINE_4_SIZE)
        self._close_btn = IconButton(
            icon=Icons.CLOSE,
            icon_size=dimens.ICON_SIZE,
            icon_color=colors.text_secondary,
            tooltip="Close",
            on_click=lambda e: self.close(),
        )
        self._edit_btn = IconButton(
            icon=Icons.EDIT_OUTLINED,
            icon_size=dimens.ICON_SIZE,
            icon_color=colors.text_secondary,
            tooltip="Edit",
            on_click=lambda e: self._switch_to_edit(),
        )
        self._header = Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=CrossAxisAlignment.CENTER,
            controls=[
                self._title_text,
                Row(
                    spacing=0,
                    controls=[self._edit_btn, self._close_btn],
                ),
            ],
        )

        # Scrollable body
        self._body = ListView(expand=True, spacing=dimens.SPACE_XS)

        super().__init__(
            visible=False,
            width=400,
            bgcolor=colors.bg_surface,
            border=Border(left=BorderSide(1, colors.border)),
            border_radius=BorderRadius(
                top_left=dimens.RADIUS_LG,
                bottom_left=dimens.RADIUS_LG,
                top_right=0,
                bottom_right=0,
            ),
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_MD, vertical=dimens.SPACE_SM
            ),
            content=Column(
                expand=True,
                spacing=0,
                controls=[
                    self._header,
                    Container(height=dimens.SPACE_XS),
                    self._body,
                ],
            ),
        )

    # -- Public API -----------------------------------------------------------

    def show_detail(self, entity, title: str = ""):
        """Open the panel in view mode for *entity*."""
        self._entity = entity
        self._mode = "view"
        self._title_text.value = title or str(entity)
        self._edit_btn.visible = True
        self._body.controls = self.build_detail_content(entity)
        self.visible = True

    def show_editor(self, entity=None, title: str = ""):
        """Open the panel in edit mode, optionally pre-filled with *entity*."""
        self._entity = entity
        self._mode = "edit"
        is_new = entity is None
        self._title_text.value = title or ("New" if is_new else "Edit")
        self._edit_btn.visible = False
        self._body.controls = self.build_edit_content(entity)
        self.visible = True

    def close(self):
        """Hide the panel and notify the parent."""
        self.visible = False
        self._body.controls.clear()
        self._entity = None
        self._on_close()

    def update(self):
        """Safe update — routes through inline container when panel isn't mounted."""
        try:
            super().update()
        except Exception:
            if self._inline_container and self._inline_container.page:
                self._inline_container.update()

    # -- Subclass hooks -------------------------------------------------------

    def build_detail_content(self, entity) -> list[Control]:
        """Return controls for the read-only detail view. Override me."""
        return [TBodyText(txt=str(entity))]

    def build_compact_detail(self, entity) -> list[Control]:
        """Return controls for compact inline detail. Override for grid layouts.

        Defaults to build_detail_content(). Override in subclasses to use
        multi-column ResponsiveRow layouts optimised for full-width inline
        display.
        """
        return self.build_detail_content(entity)

    def _compact_field(self, label: str, value: str, col: dict = None) -> Column:
        """A label + value pair sized for ResponsiveRow columns."""
        if col is None:
            col = {"xs": 6, "sm": 4, "md": 3}
        return Column(
            col=col,
            spacing=1,
            controls=[
                Text(
                    label,
                    size=fonts.CAPTION_SIZE,
                    color=colors.text_muted,
                    weight=FontWeight.W_600,
                ),
                Text(
                    value or "—",
                    size=fonts.BODY_2_SIZE,
                    color=colors.text_primary if value else colors.text_muted,
                ),
            ],
        )

    def build_edit_content(self, entity) -> list[Control]:
        """Return controls for the edit/create form. Override me."""
        return [TBodyText(txt="Editor not implemented")]

    @staticmethod
    def _edit_action_bar(
        save_label: str,
        on_save: Callable,
        on_cancel: Callable,
    ) -> Row:
        """Compact right-aligned Save / Cancel action bar for inline edit."""
        return Row(
            alignment=MainAxisAlignment.END,
            spacing=dimens.SPACE_SM,
            controls=[
                TextButton(
                    content=Text("Cancel", size=fonts.BODY_2_SIZE),
                    on_click=on_cancel,
                ),
                TPrimaryButton(label=save_label, on_click=on_save),
            ],
        )

    def _switch_to_edit(self):
        """Toggle from view mode to edit mode."""
        if self._on_edit_requested and self._entity:
            self._on_edit_requested(self._entity)
        elif self._entity:
            self.show_editor(self._entity, title="Edit")
            self.update()

    def _get_detail_field(self, label: str, value: str, icon=None) -> Container:
        """Helper: a styled label + value row for detail view."""
        controls = []
        if icon:
            controls.append(
                Icon(icon, size=dimens.SM_ICON_SIZE, color=colors.text_muted)
            )
        controls.append(
            Text(
                label,
                size=fonts.CAPTION_SIZE,
                color=colors.text_muted,
                weight=FontWeight.W_600,
            )
        )
        return Container(
            padding=Padding.symmetric(vertical=2),
            content=Column(
                spacing=2,
                controls=[
                    Row(spacing=dimens.SPACE_XXS, controls=controls),
                    Text(
                        value or "—",
                        size=fonts.BODY_2_SIZE,
                        color=colors.text_primary if value else colors.text_muted,
                    ),
                ],
            ),
        )

    def _get_section_divider(self) -> Container:
        """Thin horizontal divider between sections."""
        return Container(
            height=1,
            bgcolor=colors.border,
            margin=Margin.symmetric(vertical=dimens.SPACE_XS),
        )

    def _get_action_bar(self, *buttons) -> Container:
        """Bottom action bar with buttons."""
        return Container(
            padding=Padding.only(top=dimens.SPACE_SM),
            content=Row(
                spacing=dimens.SPACE_SM,
                controls=list(buttons),
            ),
        )


class CrudListView(TView, Column):
    """Base class for entity CRUD list views.

    Subclasses must set:
        - intent: the CrudIntent instance
        - entity_name: str (e.g. "project")
        - entity_name_plural: str (e.g. "projects")

    Subclasses must implement:
        - make_card(entity) -> row control

    Optional overrides:
        - get_column_headers() -> list[tuple[str, int|None]] or None
        - get_filters_view() -> Control or None (for filter bar)
        - on_add_intent_key -> str or None (res_utils intent key for add action)
        - open_add_editor(data) -> open inline editor for add
        - on_save_entity(entity) -> handle save result
        - load_extra_data() -> load additional data beyond entities
    """

    entity_name: str = ""
    entity_name_plural: str = ""
    on_add_intent_key: Optional[str] = None

    def get_sortable_fields(self) -> list[tuple[str, Callable]]:
        """Return a list of (label, key_func) for fields the user can sort by.

        Override in subclasses. Each key_func receives an entity and returns
        a comparable value. Sorting direction is toggled via a separate button.
        """
        return []

    def get_column_headers(self) -> Optional[list[tuple[str, Optional[int]]]]:
        """Return column headers as (label, width_or_None_for_expand).

        Override in subclasses. Example:
            [("Title", None), ("Client", 200), ("Dates", 180)]
        """
        return None

    def __init__(self, params: TViewParams):
        TView.__init__(self, params)
        Column.__init__(self)
        self._sort_ascending: bool = True
        self._sort_field_index: int = 0
        self.loading_indicator = TProgressBar()
        self.no_items_control = TBodyText(
            txt=f"You have not added any {self.entity_name_plural} yet",
            color=colors.text_muted,
            show=False,
        )

        sortable = self.get_sortable_fields()
        sort_control = None
        if sortable:
            self._sort_dropdown = Dropdown(
                value="0",
                options=[
                    DropdownOption(key=str(i), text=label)
                    for i, (label, _) in enumerate(sortable)
                ],
                on_select=self._on_sort_field_changed,
                width=180,
                text_size=fonts.BODY_2_SIZE,
                content_padding=Padding.symmetric(
                    horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XXS
                ),
                dense=True,
            )
            self._sort_dir_btn = IconButton(
                icon=Icons.ARROW_UPWARD,
                icon_size=dimens.ICON_SIZE,
                icon_color=colors.text_secondary,
                tooltip="Ascending",
                on_click=self._on_sort_dir_toggled,
            )
            sort_control = Row(
                spacing=0,
                vertical_alignment=CrossAxisAlignment.CENTER,
                controls=[
                    Icon(Icons.SORT, size=dimens.ICON_SIZE, color=colors.text_muted),
                    self._sort_dropdown,
                    self._sort_dir_btn,
                ],
            )

        heading_row = Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=CrossAxisAlignment.CENTER,
            controls=[
                THeading(
                    f"My {self.entity_name_plural.title()}",
                    size=fonts.HEADLINE_2_SIZE,
                    color=colors.text_secondary,
                ),
            ]
            + ([sort_control] if sort_control else []),
        )

        self.title_control = ResponsiveRow(
            controls=[
                Column(
                    col={"xs": 12},
                    controls=[
                        heading_row,
                        self.loading_indicator,
                        self.no_items_control,
                    ],
                )
            ]
        )
        self.items_container = ListView(
            expand=True,
            spacing=0,
        )
        self._selected_entity_id = None
        self._expanded_mode = None  # None | "detail" | "edit"
        self._inline_expansion = None  # cached expansion Container
        self.items_to_display = {}
        self.popup_handler = None

    # -- Subclass hooks --------------------------------------------------------

    def make_card(self, entity) -> Control:
        """Create a card control for the given entity. Must be overridden."""
        raise NotImplementedError

    def get_entity_description(self, entity) -> str:
        """Return a human-readable description for delete confirmation."""
        return str(entity)

    def get_filters_view(self) -> Optional[Control]:
        """Override to return a filter bar control."""
        return None

    def load_extra_data(self):
        """Override to load additional data beyond the main entity list."""
        pass

    def open_add_editor(self, data=None):
        """Override for inline add editor (contacts, clients)."""
        pass

    def on_save_entity(self, entity):
        """Override for inline save handling (contacts, clients)."""
        pass

    def _on_sort_field_changed(self, e):
        self._sort_field_index = int(e.control.value)
        self.refresh_list()
        self.update_self()

    def _on_sort_dir_toggled(self, e):
        self._sort_ascending = not self._sort_ascending
        self._sort_dir_btn.icon = (
            Icons.ARROW_UPWARD if self._sort_ascending else Icons.ARROW_DOWNWARD
        )
        self._sort_dir_btn.tooltip = (
            "Ascending" if self._sort_ascending else "Descending"
        )
        self.refresh_list()
        self.update_self()

    # -- Lifecycle methods (generic) -------------------------------------------

    def refresh_list(self):
        """Clears and rebuilds the items container from items_to_display."""
        self.items_container.controls.clear()
        entities = list(self.items_to_display.values())
        sortable = self.get_sortable_fields()
        if sortable and 0 <= self._sort_field_index < len(sortable):
            _, key_func = sortable[self._sort_field_index]
            entities.sort(
                key=lambda ent: (key_func(ent) is None, key_func(ent)),
                reverse=not self._sort_ascending,
            )

        # If creating a new entity (no selected row), show edit form at top
        if (
            self._expanded_mode == "edit"
            and self._selected_entity_id is None
            and self._inline_expansion is not None
        ):
            self.items_container.controls.append(self._inline_expansion)

        for entity in entities:
            card = self.make_card(entity)
            self.items_container.controls.append(card)
            # Insert inline expansion right after the selected row
            eid = getattr(entity, "id", None)
            if (
                eid is not None
                and eid == self._selected_entity_id
                and self._inline_expansion is not None
            ):
                self.items_container.controls.append(self._inline_expansion)

    def on_delete_clicked(self, entity):
        """Opens delete confirmation popup."""
        if self.popup_handler:
            self.popup_handler.close_dialog()
        desc = self.get_entity_description(entity)
        self.popup_handler = ConfirmDisplayPopUp(
            dialog_controller=self.dialog_controller,
            title="Are You Sure?",
            description=f"Are you sure you wish to delete this {self.entity_name}?\n{desc}",
            on_proceed=self.on_delete_confirmed,
            proceed_button_label="Yes! Delete",
            data_on_confirmed=entity.id,
        )
        self.popup_handler.open_dialog()

    def on_delete_confirmed(self, entity_id):
        """Deletes entity via intent, updates display."""
        self.loading_indicator.visible = True
        self.update_self()
        result = self.intent.delete(entity_id)
        is_error = not result.was_intent_successful
        msg = (
            f"{self.entity_name.title()} deleted!" if not is_error else result.error_msg
        )
        self.show_snack(msg, is_error)
        if not is_error and entity_id in self.items_to_display:
            del self.items_to_display[entity_id]
        self.refresh_list()
        self.loading_indicator.visible = False
        self.update_self()

    def on_filter_changed(self, state: EntityStates):
        """Handles filter state changes via generic intent methods."""
        if state == EntityStates.ACTIVE:
            self.items_to_display = self.intent.get_active_as_map()
        elif state == EntityStates.UPCOMING:
            self.items_to_display = self.intent.get_upcoming_as_map()
        elif state == EntityStates.COMPLETED:
            self.items_to_display = self.intent.get_completed_as_map()
        else:
            self.items_to_display = self.intent.get_all_as_map()
        self.refresh_list()
        self.update_self()

    def did_mount(self):
        self.reload_all_data()

    def parent_intent_listener(self, intent: str, data=None):
        if intent == res_utils.RELOAD_INTENT:
            self.reload_all_data()
        elif self.on_add_intent_key and intent == self.on_add_intent_key:
            self.open_add_editor(data)

    def reload_all_data(self):
        """Full reload: load entities, toggle empty message, refresh list."""
        self.mounted = True
        self.loading_indicator.visible = True
        self.update_self()
        self.load_extra_data()
        self.items_to_display = self.intent.get_all_as_map()
        count = len(self.items_to_display)
        if count == 0:
            self.no_items_control.visible = True
            self.items_container.controls.clear()
        else:
            self.no_items_control.visible = False
            self.refresh_list()
        self.loading_indicator.visible = False
        self.update_self()

    # -- Inline expansion (replaces side panel) ---------------------------------

    def get_side_panel(self) -> Optional[EntitySidePanel]:
        """Override to return a panel used as inline content builder."""
        return None

    def _collapse(self):
        """Collapse any open inline expansion."""
        self._selected_entity_id = None
        self._expanded_mode = None
        self._inline_expansion = None
        self.refresh_list()
        self.update_self()

    def _on_panel_closed(self):
        """Called when the panel's close/cancel button is pressed."""
        self._collapse()

    def _on_inline_edit_requested(self, entity):
        """Switch the inline expansion from detail to edit mode."""
        self._expanded_mode = "edit"
        self._inline_expansion = self._build_inline_expansion(entity)
        self.refresh_list()
        self.update_self()

    def open_detail_panel(self, entity):
        """Toggle inline detail expansion for *entity*."""
        eid = getattr(entity, "id", None)
        if eid == self._selected_entity_id and self._expanded_mode == "detail":
            # Already expanded — collapse
            self._collapse()
            return
        self._selected_entity_id = eid
        self._expanded_mode = "detail"
        if self._side_panel:
            self._side_panel._entity = entity
        self._inline_expansion = self._build_inline_expansion(entity)
        self.refresh_list()
        self.update_self()

    def open_edit_panel(self, entity=None):
        """Show inline edit form (new or existing entity)."""
        self._selected_entity_id = getattr(entity, "id", None) if entity else None
        self._expanded_mode = "edit"
        if self._side_panel:
            self._side_panel._entity = entity
        self._inline_expansion = self._build_inline_expansion(entity)
        self.refresh_list()
        self.update_self()

    def _build_inline_expansion(self, entity) -> Optional[Container]:
        """Build the inline detail/edit container from the panel's content."""
        if not self._side_panel:
            return None

        if self._expanded_mode == "edit":
            content_controls = self._side_panel.build_edit_content(entity)
        else:
            content_controls = self._side_panel.build_compact_detail(entity)

        expansion = Container(
            bgcolor=colors.bg_surface,
            border=Border(bottom=BorderSide(1, colors.border)),
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_LG, vertical=dimens.SPACE_SM
            ),
            content=Column(
                spacing=dimens.SPACE_XXS,
                controls=content_controls,
            ),
        )
        # Let the panel route update() calls through this container
        self._side_panel._inline_container = expansion
        return expansion

    def build(self):
        self._side_panel = self.get_side_panel()
        filters = self.get_filters_view()
        controls = [self.title_control, Spacer(md_space=True)]
        if filters:
            controls.append(filters)

        # Column header row
        col_headers = self.get_column_headers()
        if col_headers:
            header_cells = []
            for label, width in col_headers:
                cell = Text(
                    label.upper(),
                    size=fonts.CAPTION_SIZE,
                    color=colors.text_muted,
                    weight=FontWeight.W_600,
                )
                if width:
                    header_cells.append(Container(width=width, content=cell))
                else:
                    header_cells.append(Container(expand=True, content=cell))
            header_row = Container(
                padding=Padding.symmetric(
                    horizontal=dimens.SPACE_MD, vertical=dimens.SPACE_XS
                ),
                border=Border(bottom=BorderSide(1, colors.border)),
                content=Row(
                    controls=header_cells,
                    spacing=dimens.SPACE_MD,
                    vertical_alignment=CrossAxisAlignment.CENTER,
                ),
            )
            controls.append(header_row)

        list_container = Container(expand=True, content=self.items_container)
        controls.append(list_container)

        self.controls = controls

    def will_unmount(self):
        self.mounted = False
        if self.popup_handler:
            self.popup_handler.close_dialog()


class EntityDetailScreen(TView, Container):
    """Base class for entity detail/view screens.

    Subclasses must set:
        - intent: the CrudIntent instance
        - entity_name: str
        - edit_route: str (route for the editor screen)

    Subclasses must implement:
        - display_entity_data() -> populate UI controls from self.entity
        - build() -> build the UI layout
    """

    entity_name: str = ""
    edit_route: str = ""

    def __init__(self, params: TViewParams, entity_id, intent=None):
        TView.__init__(self, params)
        Container.__init__(self)
        self.entity_id = entity_id
        if intent is not None:
            self.intent = intent
        self.loading_indicator = TProgressBar()
        self.entity = None
        self.popup_handler = None

    # -- Subclass hooks --------------------------------------------------------

    def display_entity_data(self):
        """Populate UI controls from self.entity. Must be overridden."""
        raise NotImplementedError

    # -- Generic lifecycle -----------------------------------------------------

    def did_mount(self):
        self.reload_data()

    def on_resume_after_back_pressed(self):
        self.reload_data()

    def reload_data(self):
        self.mounted = True
        self.loading_indicator.visible = True
        result = self.intent.get_by_id(self.entity_id)
        if result.was_intent_successful and result.data:
            self.entity = result.data
            self.display_entity_data()
        else:
            self.show_snack(result.error_msg, is_error=True)
        self.loading_indicator.visible = False
        self.update_self()

    def on_edit_clicked(self, e=None):
        self.navigate_to_route(self.edit_route, self.entity_id)

    def on_delete_clicked(self, e=None):
        if self.popup_handler:
            self.popup_handler.close_dialog()
        self.popup_handler = ConfirmDisplayPopUp(
            dialog_controller=self.dialog_controller,
            title="Are You Sure?",
            description=f"Are you sure you wish to delete this {self.entity_name}?",
            on_proceed=self.on_delete_confirmed,
            proceed_button_label="Yes! Delete",
            data_on_confirmed=self.entity_id,
        )
        self.popup_handler.open_dialog()

    def on_delete_confirmed(self, entity_id):
        result = self.intent.delete(entity_id)
        is_err = not result.was_intent_successful
        msg = result.error_msg if is_err else f"{self.entity_name.title()} deleted!"
        self.show_snack(msg, is_err)
        if not is_err:
            self.navigate_back()

    def on_toggle_complete_status(self, e=None):
        result = self.intent.toggle_completed(self.entity)
        if result.was_intent_successful:
            self.entity = result.data
            self.display_entity_data()
        msg = (
            result.error_msg
            if not result.was_intent_successful
            else f"{self.entity_name.title()} status updated!"
        )
        self.show_snack(msg, not result.was_intent_successful)
        self.update_self()

    def on_view_client_clicked(self, e=None):
        """Opens a popup showing the client details."""
        if not self.entity or not getattr(self.entity, "client", None):
            return
        if self.popup_handler:
            self.popup_handler.close_dialog()
        from ..clients.view import ClientViewPopUp

        self.popup_handler = ClientViewPopUp(
            dialog_controller=self.dialog_controller,
            client=self.entity.client,
        )
        self.popup_handler.open_dialog()

    def get_body_element(self, label: str, control: Control) -> ResponsiveRow:
        """Helper: returns a label + control row for detail display."""
        return ResponsiveRow(
            controls=[
                Column(
                    col={"xs": 3},
                    controls=[
                        TBodyText(
                            txt=label, weight=FontWeight.BOLD, color=colors.text_muted
                        )
                    ],
                ),
                Column(
                    col={"xs": 9},
                    controls=[control],
                ),
            ]
        )

    # -- Declarative field binding ---------------------------------------------

    @staticmethod
    def _resolve_field_value(entity, accessor) -> str:
        """Resolve *accessor* against *entity* to a Flet-safe string.

        *accessor* is either a callable ``(entity) -> str`` or an attribute
        name.  For attribute names the value is auto-converted:
        ``None`` -> ``""``, ``Enum`` -> ``.value``, everything else -> ``str()``.
        """
        if callable(accessor):
            val = accessor(entity)
            return str(val) if val is not None else ""
        val = getattr(entity, accessor, None)
        if val is None:
            return ""
        if isinstance(val, Enum):
            return str(val.value)
        if isinstance(val, str):
            return val
        return str(val)

    def build_field_rows(self, specs: list[tuple]) -> list[ResponsiveRow]:
        """Create controls and layout rows from a list of field specs.

        Each spec is ``(label, accessor)`` where *accessor* is a string
        attribute name or a callable ``(entity) -> str``.

        Returns a list of ``ResponsiveRow`` controls ready to be placed in the
        layout.  Call :meth:`update_field_rows` later to populate them.
        """
        self._field_specs: list[tuple[str, typing.Any, TBodyText]] = []
        rows: list[ResponsiveRow] = []
        for label, accessor in specs:
            control = TBodyText(align=utils.TXT_ALIGN_JUSTIFY)
            self._field_specs.append((label, accessor, control))
            rows.append(self.get_body_element(label, control))
        return rows

    def update_field_rows(self, entity) -> None:
        """Refresh all controls created by :meth:`build_field_rows`."""
        for _label, accessor, control in self._field_specs:
            control.value = self._resolve_field_value(entity, accessor)

    def will_unmount(self):
        self.mounted = False
