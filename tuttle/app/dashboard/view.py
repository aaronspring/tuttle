"""Dashboard view — Flet-native business overview.

Renders KPI cards, revenue bar charts, project budget progress bars,
and financial goal tracking using only Flet controls (no browser).
"""

from decimal import Decimal

from flet import (
    Column,
    Container,
    CrossAxisAlignment,
    Icon,
    Icons,
    MainAxisAlignment,
    Padding,
    ResponsiveRow,
    Row,
    ScrollMode,
    Text,
    TextAlign,
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


# ── Revenue Bar (native) ─────────────────────────────────────


_BAR_CHART_HEIGHT = 160


class _VerticalBar(Column):
    """A single vertical bar in the revenue chart."""

    def __init__(
        self, label: str, value: float, max_value: float, is_forecast: bool = False
    ):
        ratio = min(value / max_value, 1.0) if max_value > 0 else 0
        bar_height = max(ratio * _BAR_CHART_HEIGHT, 2) if ratio > 0 else 0
        empty_height = _BAR_CHART_HEIGHT - bar_height
        bar_color = colors.accent if not is_forecast else colors.accent_muted
        value_text = fmt_currency(value) if value > 0 else ""

        super().__init__(
            expand=True,
            horizontal_alignment=CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                # Value label above bar
                Text(
                    value_text,
                    size=fonts.CAPTION_SIZE - 1,
                    color=colors.text_muted if is_forecast else colors.text_secondary,
                    text_align=TextAlign.CENTER,
                ),
                # Empty space above bar
                Container(height=empty_height),
                # The bar itself
                Container(
                    height=bar_height,
                    bgcolor=bar_color,
                    border_radius=dimens.RADIUS_SM,
                    expand=True,
                ),
                # Month label below bar
                Container(
                    padding=Padding.only(top=dimens.SPACE_XXS),
                    content=Text(
                        label,
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_muted
                        if is_forecast
                        else colors.text_secondary,
                        text_align=TextAlign.CENTER,
                    ),
                ),
            ],
        )


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
                        views.Spacer(sm_space=True),
                        self._kpi_row,
                        self._tax_row,
                        self._revenue_section,
                        self._budget_section,
                        self._goals_section,
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
        """Fetch all dashboard data and rebuild controls."""
        self._load_kpis()
        self._load_revenue_chart()
        self._load_project_budgets()
        self._load_goals()
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

    def _load_revenue_chart(self):
        self._revenue_section.controls.clear()

        result = self.intent.get_monthly_revenue(n_months=12)
        if not result.was_intent_successful or not result.data:
            return

        months = result.data
        if not months:
            return

        # Collect all bar data (history + forecast) to compute a shared max
        bar_data = []
        for m in months:
            rev = float(m["revenue"])
            if rev > 0:
                # "YYYY-MM" → "MM\n'YY"
                year, mon = m["month"].split("-")
                label = f"{mon}\n'{year[2:]}"
                bar_data.append((label, rev, False))

        # Forecast
        forecast_result = self.intent.get_revenue_curve(forecast_months=6)
        if forecast_result.was_intent_successful and forecast_result.data is not None:
            df = forecast_result.data
            forecast_rows = df[df["is_forecast"].eq(True)]
            for _, row in forecast_rows.iterrows():
                month_dt = row["month"]
                if hasattr(month_dt, "strftime"):
                    label = month_dt.strftime("%m") + "*\n'" + month_dt.strftime("%y")
                else:
                    s = str(month_dt)
                    label = s[5:7] + "*\n'" + s[2:4]
                bar_data.append((label, float(row["revenue"]), True))

        if not bar_data:
            return

        max_val = max(v for _, v, _ in bar_data)
        if max_val == 0:
            max_val = 1

        bars = [
            _VerticalBar(label, value, max_val, is_forecast=fc)
            for label, value, fc in bar_data
        ]

        self._revenue_section.controls = [
            _section_header("Monthly Revenue", Icons.BAR_CHART),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Row(
                    spacing=dimens.SPACE_XXS,
                    vertical_alignment=CrossAxisAlignment.END,
                    controls=list(bars),
                ),
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
