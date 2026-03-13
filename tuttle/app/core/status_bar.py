"""Interactive status bar — live business dashboard strip.

Inspired by VS Code's status bar: every item is clickable and
contextual, showing live business health at a glance.
"""

import datetime
from typing import Any, Callable, Optional
from dataclasses import dataclass

from flet import (
    Border,
    BorderSide,
    Container,
    Icon,
    Icons,
    Margin,
    Padding,
    PopupMenuButton,
    PopupMenuItem,
    Row,
    Text,
    MainAxisAlignment,
    CrossAxisAlignment,
)

from ..res import colors, dimens, fonts


# ── Status bar item primitives ───────────────────────────────


class StatusBarItem(Container):
    """A single clickable item in the status bar."""

    def __init__(
        self,
        icon: Optional[Any] = None,
        text: str = "",
        color: Optional[str] = None,
        tooltip: Optional[str] = None,
        on_click: Optional[Callable] = None,
        icon_size: int = dimens.SM_ICON_SIZE,
        visible: bool = True,
    ):
        text_color = color or colors.text_inverse
        controls = []
        if icon:
            controls.append(
                Icon(icon, size=icon_size, color=text_color),
            )
        controls.append(
            Text(
                text,
                size=fonts.STATUS_BAR_SIZE,
                color=text_color,
                weight=fonts.BOLD_FONT,
            ),
        )
        super().__init__(
            padding=Padding.symmetric(
                horizontal=dimens.STATUSBAR_ITEM_PADDING_H,
            ),
            on_click=on_click,
            on_hover=self._on_hover if on_click else None,
            tooltip=tooltip,
            visible=visible,
            border_radius=dimens.RADIUS_SM,
            content=Row(
                controls=controls,
                spacing=dimens.SPACE_XXS,
                vertical_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        self._text_control = controls[-1]
        self._icon_control = controls[0] if icon else None

    def _on_hover(self, e):
        self.bgcolor = "#20FFFFFF" if e.data == "true" else None
        self.update()

    def set_text(self, text: str):
        self._text_control.value = text

    def set_color(self, color: str):
        self._text_control.color = color
        if self._icon_control:
            self._icon_control.color = color

    def set_visible(self, visible: bool):
        self.visible = visible


class StatusBarDivider(Container):
    """Thin vertical divider between status bar items."""

    def __init__(self):
        super().__init__(
            width=dimens.STATUSBAR_DIVIDER_WIDTH,
            height=14,
            bgcolor="#40FFFFFF",  # 25% white
            margin=Margin.symmetric(horizontal=2),
        )


# ── StatusBarManager ─────────────────────────────────────────


@dataclass
class StatusBarData:
    """Holds the current status bar state."""

    # Left zone
    timer_running: bool = False
    timer_project: str = ""
    timer_start: Optional[datetime.datetime] = None
    today_tracked: str = ""

    # Center zone — business health warnings
    overdue_count: int = 0
    outstanding_amount: str = ""
    expiring_contracts: int = 0

    # Right zone
    entity_count: str = ""
    entity_summary: str = ""


class StatusBarManager:
    """Manages the interactive status bar content.

    Call `update_for_view()` when the active view changes,
    and `update_warnings()` to refresh business health indicators.
    """

    def __init__(
        self,
        on_click_overdue: Optional[Callable] = None,
        on_click_outstanding: Optional[Callable] = None,
        on_click_expiring: Optional[Callable] = None,
        on_click_sync: Optional[Callable] = None,
        on_click_quick_add: Optional[Callable] = None,
        on_click_settings: Optional[Callable] = None,
        on_click_profile: Optional[Callable] = None,
        on_click_help_ask: Optional[Callable] = None,
        on_click_help_bug: Optional[Callable] = None,
    ):
        self._on_click_overdue = on_click_overdue
        self._on_click_outstanding = on_click_outstanding
        self._on_click_expiring = on_click_expiring
        self._on_click_sync = on_click_sync
        self._on_click_quick_add = on_click_quick_add

        # ── Left zone items ──
        self.entity_count_item = StatusBarItem(
            text="Tuttle",
            tooltip="Current view",
        )

        # ── Center zone — warnings (hidden by default) ──
        self.overdue_item = StatusBarItem(
            icon=Icons.WARNING_AMBER_ROUNDED,
            text="0 overdue",
            color=colors.warning,
            tooltip="Click to view overdue invoices",
            on_click=on_click_overdue,
            visible=False,
        )
        self.outstanding_item = StatusBarItem(
            icon=Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
            text="€0 outstanding",
            tooltip="Click to view unpaid invoices",
            on_click=on_click_outstanding,
            visible=False,
        )
        self.expiring_item = StatusBarItem(
            icon=Icons.EVENT_BUSY_OUTLINED,
            text="0 ending soon",
            color=colors.warning,
            tooltip="Click to view expiring contracts",
            on_click=on_click_expiring,
            visible=False,
        )

        # ── Right zone items ──
        self.entity_summary_item = StatusBarItem(
            text="",
            visible=False,
        )

        self._warning_divider = StatusBarDivider()
        self._warning_divider.visible = False

        self._right_divider = StatusBarDivider()
        self._right_divider.visible = False

        # ── Chrome zone — settings, profile, help (left side) ──
        self._chrome_divider = StatusBarDivider()

        self.settings_item = StatusBarItem(
            icon=Icons.SETTINGS_OUTLINED,
            tooltip="Preferences",
            on_click=on_click_settings,
            color=colors.text_muted,
        )
        self.profile_item = StatusBarItem(
            icon=Icons.PERSON_OUTLINE_OUTLINED,
            tooltip="Profile",
            on_click=on_click_profile,
            color=colors.text_muted,
        )
        self.help_menu = PopupMenuButton(
            content=Container(
                padding=Padding.symmetric(horizontal=dimens.STATUSBAR_ITEM_PADDING_H),
                border_radius=dimens.RADIUS_SM,
                content=Row(
                    controls=[
                        Icon(
                            Icons.HELP_OUTLINE,
                            size=dimens.SM_ICON_SIZE,
                            color=colors.text_muted,
                        ),
                    ],
                    spacing=0,
                    vertical_alignment=CrossAxisAlignment.CENTER,
                ),
                on_hover=lambda e: self._on_help_hover(e),
            ),
            tooltip="Help",
            menu_padding=Padding.symmetric(vertical=4, horizontal=0),
            items=[
                PopupMenuItem(
                    height=32,
                    content=Row(
                        controls=[
                            Icon(
                                Icons.CONTACT_SUPPORT,
                                size=dimens.SM_ICON_SIZE,
                                color=colors.text_secondary,
                            ),
                            Text(
                                "Ask a question",
                                size=fonts.BODY_2_SIZE,
                                color=colors.text_primary,
                            ),
                        ],
                        spacing=dimens.SPACE_XS,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                    ),
                    on_click=on_click_help_ask,
                ),
                PopupMenuItem(
                    height=32,
                    content=Row(
                        controls=[
                            Icon(
                                Icons.BUG_REPORT,
                                size=dimens.SM_ICON_SIZE,
                                color=colors.text_secondary,
                            ),
                            Text(
                                "Report a bug",
                                size=fonts.BODY_2_SIZE,
                                color=colors.text_primary,
                            ),
                        ],
                        spacing=dimens.SPACE_XS,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                    ),
                    on_click=on_click_help_bug,
                ),
            ],
        )

        # Initialized to None; set by build()
        self.bar: Optional[Container] = None

    def _on_help_hover(self, e):
        """Hover effect for the help menu button."""
        e.control.bgcolor = "#20FFFFFF" if e.data == "true" else None
        e.control.update()

    def build(self) -> Container:
        """Build the status bar container."""
        self.bar = Container(
            height=dimens.FOOTER_HEIGHT,
            bgcolor=colors.bg_statusbar,
            border=Border(top=BorderSide(1, colors.border)),
            padding=Padding.symmetric(horizontal=dimens.SPACE_XS),
            content=Row(
                controls=[
                    # Left zone — chrome icons
                    Row(
                        controls=[
                            self.settings_item,
                            self.profile_item,
                            self.help_menu,
                        ],
                        spacing=0,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                    ),
                    # Center zone — warnings
                    Row(
                        controls=[
                            self._warning_divider,
                            self.overdue_item,
                            self.outstanding_item,
                            self.expiring_item,
                        ],
                        spacing=0,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                    ),
                    # Right zone
                    Row(
                        controls=[
                            self._right_divider,
                            self.entity_summary_item,
                        ],
                        spacing=0,
                        vertical_alignment=CrossAxisAlignment.CENTER,
                        expand=True,
                        alignment=MainAxisAlignment.END,
                    ),
                ],
                spacing=0,
                alignment=MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=CrossAxisAlignment.CENTER,
            ),
        )
        return self.bar

    def update_for_view(
        self,
        entity_count_text: str = "",
        summary_text: str = "",
    ):
        """Update status bar for the currently active view."""
        if summary_text:
            self.entity_summary_item.set_text(summary_text)
            self.entity_summary_item.visible = True
            self._right_divider.visible = True
        else:
            self.entity_summary_item.visible = False
            self._right_divider.visible = False

    def update_warnings(
        self,
        overdue_count: int = 0,
        outstanding_text: str = "",
        expiring_count: int = 0,
    ):
        """Update the business health warning indicators."""
        has_warnings = overdue_count > 0 or bool(outstanding_text) or expiring_count > 0

        # Overdue invoices
        if overdue_count > 0:
            self.overdue_item.set_text(f"{overdue_count} overdue")
            self.overdue_item.visible = True
        else:
            self.overdue_item.visible = False

        # Outstanding amount
        if outstanding_text:
            self.outstanding_item.set_text(outstanding_text)
            self.outstanding_item.visible = True
        else:
            self.outstanding_item.visible = False

        # Expiring contracts
        if expiring_count > 0:
            self.expiring_item.set_text(f"{expiring_count} ending soon")
            self.expiring_item.visible = True
        else:
            self.expiring_item.visible = False

        self._warning_divider.visible = has_warnings

        # Update bar color based on urgency
        if self.bar is not None:
            if overdue_count > 0:
                self.bar.bgcolor = colors.bg_statusbar_danger
            elif has_warnings:
                self.bar.bgcolor = colors.bg_statusbar_warning
            else:
                self.bar.bgcolor = colors.bg_statusbar

    def try_update(self):
        """Try to push visual updates to the bar."""
        if self.bar is None:
            return
        try:
            self.bar.update()
        except Exception:
            pass
