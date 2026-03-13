"""Dashboard view — Flet-native business overview.

Renders KPI cards, revenue bar charts, project budget progress bars,
and financial goal tracking using only Flet controls (no browser).
"""

import threading
from decimal import Decimal

import flet_charts as fch
from flet import (
    Border,
    BorderRadius,
    BorderSide,
    Colors,
    Column,
    Container,
    CrossAxisAlignment,
    Icon,
    Icons,
    MainAxisAlignment,
    Padding,
    ProgressRing,
    ResponsiveRow,
    Row,
    ScrollMode,
    Text,
    TextStyle,
)

from ..core.abstractions import TView, TViewParams
from ..core import views
from ..core.utils import fmt_currency
from ..res import colors, dimens, fonts, res_utils
from .intent import DashboardIntent


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}%"


# ── KPI Card ──────────────────────────────────────────────────


class _KPICard(Container):
    """A single KPI metric card."""

    def __init__(
        self,
        title: str,
        value: str,
        icon=Icons.INFO_OUTLINE,
        value_color: str = colors.text_primary,
    ):
        super().__init__(
            bgcolor=colors.bg_surface,
            border_radius=dimens.RADIUS_LG,
            padding=Padding.all(dimens.SPACE_SM),
            col={"xs": 12, "sm": 6, "md": 4, "lg": 3},
            content=Column(
                spacing=dimens.SPACE_XS,
                controls=[
                    Row(
                        spacing=dimens.SPACE_XS,
                        controls=[
                            Icon(
                                icon, size=dimens.SM_ICON_SIZE, color=colors.text_muted
                            ),
                            Text(
                                title.upper(),
                                size=fonts.CAPTION_SIZE,
                                color=colors.text_muted,
                                weight=fonts.BOLD_FONT,
                                style=TextStyle(letter_spacing=0.8),
                            ),
                        ],
                    ),
                    Text(
                        value,
                        size=fonts.HEADLINE_2_SIZE,
                        color=value_color,
                        weight=fonts.BOLDER_FONT,
                    ),
                ],
            ),
        )


_BAR_CHART_HEIGHT = 260


# ── Project Budget Row ────────────────────────────────────────


class _ProjectBudgetRow(Container):
    """Progress bar for a single project's budget utilization."""

    def __init__(
        self,
        project_name: str,
        progress: float,
        hours_tracked: float,
        hours_budget: float,
    ):
        progress = min(progress, 1.0)
        bar_color = (
            colors.success
            if progress < 0.8
            else (colors.warning if progress < 1.0 else colors.danger)
        )

        super().__init__(
            padding=Padding.symmetric(vertical=dimens.SPACE_XXS),
            content=Column(
                spacing=2,
                controls=[
                    Row(
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            Text(
                                project_name,
                                size=fonts.BODY_1_SIZE,
                                color=colors.text_primary,
                                expand=True,
                            ),
                            Text(
                                f"{hours_tracked:.0f} / {hours_budget:.0f} h ({_fmt_pct(progress)})",
                                size=fonts.BODY_2_SIZE,
                                color=colors.text_secondary,
                            ),
                        ],
                    ),
                    Container(
                        height=6,
                        bgcolor=colors.border,
                        border_radius=dimens.RADIUS_PILL,
                        content=Row(
                            spacing=0,
                            controls=[
                                Container(
                                    expand=int(max(progress * 100, 1)),
                                    height=6,
                                    bgcolor=bar_color,
                                    border_radius=dimens.RADIUS_PILL,
                                ),
                                Container(expand=int(max((1 - progress) * 100, 0))),
                            ],
                        ),
                    ),
                ],
            ),
        )


# ── Section Header ────────────────────────────────────────────


def _section_header(title: str, icon=None) -> Container:
    controls = []
    if icon:
        controls.append(
            Icon(icon, size=dimens.MD_ICON_SIZE, color=colors.text_secondary)
        )
    controls.append(
        Text(
            title,
            size=fonts.HEADLINE_4_SIZE,
            color=colors.text_primary,
            weight=fonts.BOLD_FONT,
        )
    )
    return Container(
        padding=Padding.only(top=dimens.SPACE_MD, bottom=dimens.SPACE_XS),
        content=Row(spacing=dimens.SPACE_XS, controls=controls),
    )


# ── Main Dashboard View ──────────────────────────────────────


class DashboardView(TView, Column):
    """Freelance business dashboard — the default landing view."""

    def __init__(self, params: TViewParams):
        TView.__init__(self, params)
        Column.__init__(self)
        self.intent = DashboardIntent()
        self.scroll = ScrollMode.AUTO
        self.spacing = 0
        self.expand = True

    def build(self):
        self._kpi_row = ResponsiveRow(
            spacing=dimens.SPACE_SM, run_spacing=dimens.SPACE_SM
        )
        self._tax_row = ResponsiveRow(
            spacing=dimens.SPACE_SM, run_spacing=dimens.SPACE_SM
        )
        self._revenue_section = Column(spacing=0)
        self._budget_section = Column(spacing=0)
        self._goals_section = Column(spacing=0)
        self._spinner = ProgressRing(
            width=32, height=32, stroke_width=3, color=colors.accent
        )
        self._content = Column(
            spacing=dimens.SPACE_XS,
            visible=False,
            controls=[
                views.Spacer(sm_space=True),
                self._kpi_row,
                self._tax_row,
                self._revenue_section,
                self._budget_section,
                self._goals_section,
            ],
        )

        self.controls = [
            Container(
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(
                    spacing=dimens.SPACE_XS,
                    controls=[
                        Text(
                            "Dashboard",
                            size=fonts.HEADLING_1_SIZE,
                            color=colors.text_primary,
                            weight=fonts.BOLDER_FONT,
                        ),
                        Row(
                            alignment=MainAxisAlignment.CENTER,
                            controls=[self._spinner],
                        ),
                        self._content,
                    ],
                ),
            )
        ]

    def did_mount(self):
        self.mounted = True
        self._load_data()

    def on_resume_after_back_pressed(self):
        self._load_data()

    def parent_intent_listener(self, intent: str, data=None):
        if intent == res_utils.RELOAD_INTENT:
            self._load_data()

    def _load_data(self):
        """Kick off data loading in a background thread to keep the UI responsive."""
        self._spinner.visible = True
        self._content.visible = False
        self.update_self()
        threading.Thread(target=self._load_data_sync, daemon=True).start()

    def _load_data_sync(self):
        """Fetch all dashboard data and rebuild controls (runs off-UI-thread)."""
        self._load_kpis()
        self._load_monthly_chart()
        self._load_project_budgets()
        self._load_goals()
        self._spinner.visible = False
        self._content.visible = True
        self.update_self()

    # ── KPI cards ─────────────────────────────────────────────

    def _load_kpis(self):
        result = self.intent.get_kpis()
        self._kpi_row.controls.clear()
        if not result.was_intent_successful or result.data is None:
            return

        kpis = result.data
        tc = kpis.tax_currency
        cards = [
            _KPICard(
                "Revenue (YTD)",
                fmt_currency(kpis.total_revenue_ytd, tc),
                Icons.TRENDING_UP,
                colors.success if kpis.total_revenue_ytd > 0 else colors.text_primary,
            ),
            _KPICard(
                "Outstanding",
                fmt_currency(kpis.outstanding_amount, tc),
                Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                colors.warning if kpis.outstanding_amount > 0 else colors.text_primary,
            ),
            _KPICard(
                "Overdue",
                fmt_currency(kpis.overdue_amount, tc),
                Icons.WARNING_AMBER_ROUNDED,
                colors.danger if kpis.overdue_amount > 0 else colors.text_primary,
            ),
            _KPICard(
                "Eff. Hourly Rate",
                fmt_currency(kpis.effective_hourly_rate, tc)
                if kpis.effective_hourly_rate
                else "—",
                Icons.SPEED,
                colors.accent,
            ),
            _KPICard(
                "Utilization",
                _fmt_pct(kpis.utilization_rate),
                Icons.PIE_CHART_OUTLINE,
                colors.accent
                if kpis.utilization_rate and kpis.utilization_rate >= 0.7
                else colors.warning,
            ),
            _KPICard(
                "Active Projects",
                str(kpis.active_projects),
                Icons.WORK_OUTLINE,
            ),
            _KPICard(
                "Active Contracts",
                str(kpis.active_contracts),
                Icons.HANDSHAKE_OUTLINED,
            ),
            _KPICard(
                "Unpaid Invoices",
                str(kpis.unpaid_invoices),
                Icons.RECEIPT_OUTLINED,
                colors.warning if kpis.unpaid_invoices > 0 else colors.text_primary,
            ),
        ]
        self._kpi_row.controls.extend(cards)

        tax_cards = [
            _KPICard(
                "VAT Reserve",
                fmt_currency(kpis.vat_reserve, tc),
                Icons.ACCOUNT_BALANCE,
                colors.warning if kpis.vat_reserve > 0 else colors.text_primary,
            ),
            _KPICard(
                "Est. Income Tax",
                fmt_currency(kpis.income_tax_reserve, tc),
                Icons.CALCULATE_OUTLINED,
                colors.warning if kpis.income_tax_reserve > 0 else colors.text_primary,
            ),
            _KPICard(
                "Spendable Income",
                fmt_currency(kpis.spendable_income, tc),
                Icons.SAVINGS_OUTLINED,
                colors.success if kpis.spendable_income > 0 else colors.danger,
            ),
        ]
        self._tax_row.controls.clear()
        self._tax_row.controls.extend(tax_cards)

    # ── Revenue chart ─────────────────────────────────────────

    def _build_chart_legend_chip(self, label: str, color: str) -> Container:
        return Container(
            bgcolor=colors.bg_input,
            border_radius=dimens.RADIUS_PILL,
            padding=Padding.symmetric(
                horizontal=dimens.SPACE_SM, vertical=dimens.SPACE_XXS
            ),
            content=Row(
                spacing=dimens.SPACE_XXS,
                controls=[
                    Container(
                        width=8,
                        height=8,
                        bgcolor=color,
                        border_radius=dimens.RADIUS_PILL,
                    ),
                    Text(
                        label,
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_secondary,
                    ),
                ],
            ),
        )

    def _load_monthly_chart(self):
        self._revenue_section.controls.clear()
        result = self.intent.get_monthly_chart_data(n_months=12)
        if not result.was_intent_successful or not result.data:
            return

        revenue_by_month = {m["month"]: m for m in result.data["revenue"]}
        spendable_by_month = {m["month"]: m for m in result.data["spendable"]}
        month_keys = sorted(
            set(revenue_by_month.keys()) & set(spendable_by_month.keys())
        )
        if not month_keys:
            return

        groups = []
        bottom_labels = []
        max_val = 0.0
        for idx, mk in enumerate(month_keys):
            y, m = mk.split("-")
            label = f"{m}/{y[2:]}"
            rev = float(revenue_by_month[mk]["revenue"])
            sp = float(spendable_by_month[mk]["spendable"])
            max_val = max(max_val, abs(rev), abs(sp))

            sp_color = colors.success if sp >= 0 else colors.danger
            groups.append(
                fch.BarChartGroup(
                    x=idx,
                    rods=[
                        fch.BarChartRod(
                            from_y=0,
                            to_y=rev,
                            width=16,
                            color=colors.accent,
                            tooltip=fch.BarChartRodTooltip(
                                f"Revenue: {fmt_currency(rev)}",
                                text_style=TextStyle(color=Colors.WHITE, size=13),
                            ),
                            border_radius=2,
                        ),
                        fch.BarChartRod(
                            from_y=0,
                            to_y=sp,
                            width=16,
                            color=sp_color,
                            tooltip=fch.BarChartRodTooltip(
                                f"Spendable: {fmt_currency(sp)}",
                                text_style=TextStyle(color=Colors.WHITE, size=13),
                            ),
                            border_radius=2,
                        ),
                    ],
                )
            )
            bottom_labels.append(
                fch.ChartAxisLabel(
                    value=idx,
                    label=Container(
                        Text(
                            label, size=fonts.CAPTION_SIZE, color=colors.text_secondary
                        ),
                        padding=Padding.only(top=4),
                    ),
                )
            )

        chart = fch.BarChart(
            expand=True,
            height=_BAR_CHART_HEIGHT,
            interactive=True,
            max_y=max_val * 1.1 if max_val > 0 else 100,
            min_y=0,
            groups=groups,
            group_spacing=8,
            tooltip=fch.BarChartTooltip(
                bgcolor=Colors.with_opacity(0.9, Colors.GREY_900),
                border_radius=BorderRadius.all(8),
                padding=Padding.symmetric(horizontal=12, vertical=8),
            ),
            border=Border(
                bottom=BorderSide(width=1, color=colors.border),
                left=BorderSide(width=1, color=colors.border),
            ),
            horizontal_grid_lines=fch.ChartGridLines(
                color=colors.border, width=0.5, dash_pattern=[4, 4]
            ),
            left_axis=fch.ChartAxis(label_size=50),
            bottom_axis=fch.ChartAxis(label_size=30, labels=bottom_labels),
        )

        self._revenue_section.controls = [
            Container(
                padding=Padding.only(top=dimens.SPACE_MD, bottom=dimens.SPACE_XS),
                content=Row(
                    alignment=MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=CrossAxisAlignment.CENTER,
                    controls=[
                        Row(
                            spacing=dimens.SPACE_XS,
                            controls=[
                                Icon(
                                    Icons.BAR_CHART,
                                    size=dimens.MD_ICON_SIZE,
                                    color=colors.text_secondary,
                                ),
                                Text(
                                    "Monthly Revenue vs Spendable Income (Est.)",
                                    size=fonts.HEADLINE_4_SIZE,
                                    color=colors.text_primary,
                                    weight=fonts.BOLD_FONT,
                                ),
                            ],
                        ),
                        Row(
                            spacing=dimens.SPACE_XXS,
                            controls=[
                                self._build_chart_legend_chip("Revenue", colors.accent),
                                self._build_chart_legend_chip(
                                    "Spendable", colors.success
                                ),
                            ],
                        ),
                    ],
                ),
            ),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=chart,
            ),
        ]

    # ── Project budgets ───────────────────────────────────────

    def _load_project_budgets(self):
        self._budget_section.controls.clear()

        result = self.intent.get_project_budgets()
        if not result.was_intent_successful or not result.data:
            return

        rows = [
            _ProjectBudgetRow(
                b["project"],
                b["progress"],
                b["hours_tracked"],
                b["hours_budget"],
            )
            for b in result.data
        ]

        if not rows:
            return

        self._budget_section.controls = [
            _section_header("Project Budgets", Icons.DONUT_LARGE),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(spacing=dimens.SPACE_XS, controls=list(rows)),
            ),
        ]

    # ── Financial goals ───────────────────────────────────────

    def _load_goals(self):
        self._goals_section.controls.clear()

        result = self.intent.get_financial_goals()
        if not result.was_intent_successful or not result.data:
            return

        goals = result.data
        if not goals:
            return

        kpi_result = self.intent.get_kpis()
        ytd_revenue = Decimal(0)
        tc = "EUR"
        if kpi_result.was_intent_successful and kpi_result.data:
            ytd_revenue = kpi_result.data.total_revenue_ytd
            tc = kpi_result.data.tax_currency

        goal_rows = []
        for goal in goals:
            progress = (
                float(ytd_revenue / goal.target_amount) if goal.target_amount > 0 else 0
            )
            progress = min(progress, 1.0)
            bar_color = (
                colors.success
                if goal.is_reached
                else (colors.accent if progress < 1.0 else colors.success)
            )
            status_text = (
                "Reached!"
                if goal.is_reached
                else f"{fmt_currency(ytd_revenue, tc)} / {fmt_currency(goal.target_amount, tc)}"
            )

            goal_rows.append(
                Container(
                    padding=Padding.symmetric(vertical=dimens.SPACE_XXS),
                    content=Column(
                        spacing=2,
                        controls=[
                            Row(
                                alignment=MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    Text(
                                        goal.title,
                                        size=fonts.BODY_1_SIZE,
                                        color=colors.text_primary,
                                        expand=True,
                                    ),
                                    Text(
                                        status_text,
                                        size=fonts.BODY_2_SIZE,
                                        color=colors.success
                                        if goal.is_reached
                                        else colors.text_secondary,
                                    ),
                                ],
                            ),
                            Row(
                                alignment=MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    Text(
                                        f"Target: {fmt_currency(goal.target_amount, tc)} by {goal.target_date.strftime('%b %Y')}",
                                        size=fonts.CAPTION_SIZE,
                                        color=colors.text_muted,
                                    ),
                                ],
                            ),
                            Container(
                                height=6,
                                bgcolor=colors.border,
                                border_radius=dimens.RADIUS_PILL,
                                content=Row(
                                    spacing=0,
                                    controls=[
                                        Container(
                                            expand=int(max(progress * 100, 1)),
                                            height=6,
                                            bgcolor=bar_color,
                                            border_radius=dimens.RADIUS_PILL,
                                        ),
                                        Container(
                                            expand=int(max((1 - progress) * 100, 0))
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            )

        self._goals_section.controls = [
            _section_header("Financial Goals", Icons.FLAG_OUTLINED),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(spacing=dimens.SPACE_SM, controls=goal_rows),
            ),
        ]
