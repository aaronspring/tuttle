"""Tax planning view — Flet-native tax reserve breakdown.

Sections:
1. Revenue Waterfall: gross → minus VAT → minus income tax → spendable
2. Quarterly VAT table
3. Income Tax Brackets visualization
"""

from decimal import Decimal

from flet import (
    Column,
    Container,
    Divider,
    Icon,
    Icons,
    MainAxisAlignment,
    Padding,
    Row,
    ScrollMode,
    Text,
    TextAlign,
)

from ..core.abstractions import TView, TViewParams
from ..core import views
from ..core.utils import fmt_currency
from ..res import colors, dimens, fonts, res_utils
from .intent import TaxIntent


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


# ── Waterfall Bar ─────────────────────────────────────────────


class _WaterfallItem(Container):
    """A single item in the revenue waterfall."""

    def __init__(
        self,
        label: str,
        amount: Decimal,
        total: Decimal,
        bar_color: str,
        is_total: bool = False,
        currency: str = "EUR",
    ):
        ratio = float(abs(amount) / total) if total > 0 else 0
        bar_width_pct = max(ratio, 0.02)  # minimum visible width

        sign = "" if amount >= 0 or is_total else "−"
        display_amount = abs(amount)

        super().__init__(
            padding=Padding.symmetric(vertical=dimens.SPACE_XS),
            content=Column(
                spacing=2,
                controls=[
                    Row(
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            Text(
                                label,
                                size=fonts.BODY_1_SIZE,
                                color=colors.text_primary,
                                weight=fonts.BOLD_FONT if is_total else None,
                            ),
                            Text(
                                f"{sign}{fmt_currency(display_amount, currency)}",
                                size=fonts.BODY_1_SIZE,
                                color=bar_color,
                                weight=fonts.BOLD_FONT if is_total else None,
                            ),
                        ],
                    ),
                    Container(
                        height=8 if not is_total else 10,
                        bgcolor=colors.border,
                        border_radius=dimens.RADIUS_SM,
                        content=Row(
                            spacing=0,
                            controls=[
                                Container(
                                    expand=int(max(bar_width_pct * 100, 1)),
                                    height=8 if not is_total else 10,
                                    bgcolor=bar_color,
                                    border_radius=dimens.RADIUS_SM,
                                ),
                                Container(
                                    expand=int(max((1 - bar_width_pct) * 100, 0))
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )


# ── Section Header (reused pattern) ──────────────────────────


def _section_header(title: str, icon=None) -> Container:
    ctrl = []
    if icon:
        ctrl.append(Icon(icon, size=dimens.MD_ICON_SIZE, color=colors.text_secondary))
    ctrl.append(
        Text(
            title,
            size=fonts.HEADLINE_4_SIZE,
            color=colors.text_primary,
            weight=fonts.BOLD_FONT,
        )
    )
    return Container(
        padding=Padding.only(top=dimens.SPACE_LG, bottom=dimens.SPACE_SM),
        content=Row(spacing=dimens.SPACE_XS, controls=ctrl),
    )


# ── Main Tax View ────────────────────────────────────────────


class TaxView(TView, Column):
    """Tax planning & reserve tracking view."""

    def __init__(self, params: TViewParams):
        TView.__init__(self, params)
        Column.__init__(self)
        self.intent = TaxIntent()
        self.scroll = ScrollMode.AUTO
        self.spacing = 0
        self.expand = True

    def build(self):
        self._waterfall_section = Column(spacing=0)
        self._vat_section = Column(spacing=0)
        self._bracket_section = Column(spacing=0)

        self.controls = [
            Container(
                padding=Padding.all(dimens.SPACE_MD),
                content=Column(
                    spacing=dimens.SPACE_XS,
                    controls=[
                        views.THeading("Tax & Reserves", size=fonts.HEADLINE_3_SIZE),
                        Text(
                            "How much of your revenue can you actually spend?",
                            size=fonts.BODY_1_SIZE,
                            color=colors.text_muted,
                        ),
                        views.Spacer(sm_space=True),
                        self._waterfall_section,
                        self._vat_section,
                        self._bracket_section,
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
        self._load_waterfall()
        self._load_quarterly_vat()
        self._load_bracket_info()
        self.update_self()

    # ── Revenue waterfall ─────────────────────────────────────

    def _load_waterfall(self):
        self._waterfall_section.controls.clear()
        result = self.intent.get_spendable_income()
        if not result.was_intent_successful or result.data is None:
            return

        s = result.data["spending"]
        currency = result.data.get("currency", "EUR")
        gross = s.gross_revenue_ytd
        if gross <= 0:
            self._waterfall_section.controls = [
                _section_header("Revenue Breakdown (YTD)", Icons.WATERFALL_CHART),
                Container(
                    bgcolor=colors.bg_surface,
                    border_radius=dimens.RADIUS_LG,
                    padding=Padding.all(dimens.SPACE_STD),
                    content=Text(
                        "No revenue data yet.",
                        size=fonts.BODY_1_SIZE,
                        color=colors.text_muted,
                    ),
                ),
            ]
            return

        items = [
            _WaterfallItem(
                "Gross Revenue", gross, gross, colors.accent, currency=currency
            ),
            _WaterfallItem(
                "VAT (to remit)",
                s.vat_reserve,
                gross,
                colors.warning,
                currency=currency,
            ),
            _WaterfallItem(
                "Est. Income Tax + Soli",
                s.income_tax_reserve,
                gross,
                colors.warning,
                currency=currency,
            ),
        ]

        spendable_color = colors.success if s.spendable > 0 else colors.danger
        items.append(
            _WaterfallItem(
                "= Spendable Income",
                s.spendable,
                gross,
                spendable_color,
                is_total=True,
                currency=currency,
            )
        )

        # Effective tax rate summary
        total_deductions = s.vat_reserve + s.income_tax_reserve
        effective_rate = float(total_deductions / gross) if gross > 0 else 0

        self._waterfall_section.controls = [
            _section_header("Revenue Breakdown (YTD)", Icons.WATERFALL_CHART),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(
                    spacing=0,
                    controls=[
                        *items,
                        Container(height=dimens.SPACE_SM),
                        Divider(color=colors.border, height=1),
                        Container(height=dimens.SPACE_SM),
                        Row(
                            alignment=MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                Text(
                                    "Effective reserve rate",
                                    size=fonts.CAPTION_SIZE,
                                    color=colors.text_muted,
                                ),
                                Text(
                                    f"{effective_rate:.1%} of gross revenue",
                                    size=fonts.CAPTION_SIZE,
                                    color=colors.text_secondary,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ]

    # ── Quarterly VAT ─────────────────────────────────────────

    def _load_quarterly_vat(self):
        self._vat_section.controls.clear()
        result = self.intent.get_quarterly_vat()
        if not result.was_intent_successful or not result.data:
            return

        quarters = result.data["quarters"]
        currency = result.data.get("currency", "EUR")

        # Table header
        header = Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                Container(
                    width=60,
                    content=Text(
                        "Quarter",
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_muted,
                        weight=fonts.BOLD_FONT,
                    ),
                ),
                Container(
                    width=100,
                    content=Text(
                        "Period",
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_muted,
                        weight=fonts.BOLD_FONT,
                    ),
                ),
                Container(
                    width=60,
                    content=Text(
                        "Invoices",
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_muted,
                        weight=fonts.BOLD_FONT,
                        text_align=TextAlign.RIGHT,
                    ),
                ),
                Container(
                    expand=True,
                    content=Text(
                        "VAT Collected",
                        size=fonts.CAPTION_SIZE,
                        color=colors.text_muted,
                        weight=fonts.BOLD_FONT,
                        text_align=TextAlign.RIGHT,
                    ),
                ),
            ],
        )

        # Table rows
        rows = [header, Divider(color=colors.border, height=1)]
        total_vat = Decimal(0)
        for q in quarters:
            total_vat += q["vat_collected"]
            period = (
                f"{q['period_start'].strftime('%b')} – {q['period_end'].strftime('%b')}"
            )
            vat_color = colors.warning if q["vat_collected"] > 0 else colors.text_muted
            rows.append(
                Row(
                    alignment=MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        Container(
                            width=60,
                            content=Text(
                                q["quarter"],
                                size=fonts.BODY_1_SIZE,
                                color=colors.text_primary,
                                weight=fonts.BOLD_FONT,
                            ),
                        ),
                        Container(
                            width=100,
                            content=Text(
                                period,
                                size=fonts.BODY_2_SIZE,
                                color=colors.text_secondary,
                            ),
                        ),
                        Container(
                            width=60,
                            content=Text(
                                str(q["invoice_count"]),
                                size=fonts.BODY_1_SIZE,
                                color=colors.text_primary,
                                text_align=TextAlign.RIGHT,
                            ),
                        ),
                        Container(
                            expand=True,
                            content=Text(
                                fmt_currency(q["vat_collected"], currency),
                                size=fonts.BODY_1_SIZE,
                                color=vat_color,
                                text_align=TextAlign.RIGHT,
                            ),
                        ),
                    ],
                )
            )

        # Total row
        rows.append(Divider(color=colors.border, height=1))
        rows.append(
            Row(
                alignment=MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    Text(
                        "Total",
                        size=fonts.BODY_1_SIZE,
                        color=colors.text_primary,
                        weight=fonts.BOLD_FONT,
                    ),
                    Text(
                        fmt_currency(total_vat, currency),
                        size=fonts.BODY_1_SIZE,
                        color=colors.warning if total_vat > 0 else colors.text_muted,
                        weight=fonts.BOLD_FONT,
                    ),
                ],
            )
        )

        self._vat_section.controls = [
            _section_header("Quarterly VAT", Icons.RECEIPT_LONG_OUTLINED),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(spacing=dimens.SPACE_XS, controls=rows),
            ),
        ]

    # ── Income tax brackets ───────────────────────────────────

    def _load_bracket_info(self):
        self._bracket_section.controls.clear()
        result = self.intent.get_income_tax_estimate()
        if not result.was_intent_successful or result.data is None:
            return

        data = result.data
        tax_reserve = data["tax_reserve"]
        annualized = data["annualized_income"]
        brackets = data["brackets"]
        country = data["country"]
        country_supported = data.get("country_supported", True)
        currency = data.get("currency", "EUR")

        summary_items = [
            (
                "Annualized Income",
                fmt_currency(annualized, currency),
                colors.text_primary,
            ),
        ]
        if country_supported:
            summary_items += [
                (
                    "Estimated Income Tax",
                    fmt_currency(tax_reserve.estimated_annual_tax, currency),
                    colors.warning,
                ),
                (
                    "Solidarity Surcharge",
                    fmt_currency(tax_reserve.solidarity_surcharge, currency),
                    colors.warning,
                ),
                (
                    "Total Annual Reserve",
                    fmt_currency(tax_reserve.total_annual_reserve, currency),
                    colors.warning,
                ),
                (
                    "Effective Tax Rate",
                    _fmt_pct(tax_reserve.effective_rate),
                    colors.text_secondary,
                ),
            ]

        summary_rows = []
        for label, value, color in summary_items:
            summary_rows.append(
                Row(
                    alignment=MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        Text(
                            label,
                            size=fonts.BODY_1_SIZE,
                            color=colors.text_secondary,
                        ),
                        Text(
                            value,
                            size=fonts.BODY_1_SIZE,
                            color=color,
                            weight=fonts.BOLD_FONT,
                        ),
                    ],
                )
            )

        # Bracket visualization
        bracket_rows = []
        for b in brackets:
            is_current = b["is_current"]
            bg = colors.accent if is_current else colors.bg_surface
            text_color = colors.text_inverse if is_current else colors.text_secondary
            label_weight = fonts.BOLD_FONT if is_current else None

            range_start = fmt_currency(b["start"], currency)
            range_end = fmt_currency(b["end"], currency)
            range_text = f"{range_start} – {range_end}"
            indicator = " ◄ You are here" if is_current else ""

            bracket_rows.append(
                Container(
                    bgcolor=bg,
                    border_radius=dimens.RADIUS_SM,
                    padding=Padding.symmetric(
                        horizontal=dimens.SPACE_SM,
                        vertical=dimens.SPACE_XS,
                    ),
                    content=Row(
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            Text(
                                b["label"],
                                size=fonts.BODY_2_SIZE,
                                color=text_color,
                                weight=label_weight,
                            ),
                            Text(
                                range_text + indicator,
                                size=fonts.BODY_2_SIZE,
                                color=text_color,
                            ),
                        ],
                    ),
                )
            )

        bracket_controls = [
            *summary_rows,
        ]
        if brackets:
            bracket_controls += [
                Container(height=dimens.SPACE_SM),
                Text(
                    "Tax Brackets",
                    size=fonts.CAPTION_SIZE,
                    color=colors.text_muted,
                    weight=fonts.BOLD_FONT,
                ),
                *bracket_rows,
            ]
        elif not country_supported:
            bracket_controls.append(
                Container(
                    padding=Padding.only(top=dimens.SPACE_SM),
                    content=Text(
                        f"Income tax estimation is not yet available for {country}. "
                        "VAT reserves are still tracked above.",
                        size=fonts.BODY_2_SIZE,
                        color=colors.text_muted,
                        italic=True,
                    ),
                )
            )

        self._bracket_section.controls = [
            _section_header(
                f"Income Tax Estimate ({country})",
                Icons.CALCULATE_OUTLINED,
            ),
            Container(
                bgcolor=colors.bg_surface,
                border_radius=dimens.RADIUS_LG,
                padding=Padding.all(dimens.SPACE_STD),
                content=Column(
                    spacing=dimens.SPACE_SM,
                    controls=bracket_controls,
                ),
            ),
        ]
