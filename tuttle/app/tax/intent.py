"""Business logic for the Tax view."""

from decimal import Decimal

from ..core.abstractions import SQLModelDataSourceMixin, Intent
from ..core.intent_result import IntentResult

from ...model import Invoice, User
from ...tax import get_tax_system
from ...tax_reserves import (
    compute_spendable_income,
    compute_income_tax_reserve,
    quarterly_vat_breakdown,
)


class TaxIntent(SQLModelDataSourceMixin, Intent):
    """Gathers tax-related data for the freelance tax planning view."""

    def __init__(self):
        SQLModelDataSourceMixin.__init__(self)

    def _get_country(self) -> str:
        """Determine the user's operating country for tax purposes."""
        try:
            users = self.query(User)
            if users and users[0].operating_country:
                return users[0].operating_country
        except Exception:
            pass
        return "Germany"

    def _get_tax_currency(self, country: str) -> str:
        """Return the ISO 4217 currency for the country's tax system."""
        try:
            return get_tax_system(country).currency
        except NotImplementedError:
            return "EUR"

    def get_spendable_income(self) -> IntentResult:
        """Compute spendable income breakdown."""
        try:
            invoices = self.query(Invoice)
            country = self._get_country()
            currency = self._get_tax_currency(country)
            spending = compute_spendable_income(invoices, country, currency=currency)
            data = {"spending": spending, "currency": currency}
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to compute spendable income.",
                log_message=f"TaxIntent.get_spendable_income: {e}",
                exception=e,
            )

    def get_income_tax_estimate(self) -> IntentResult:
        """Get detailed income tax estimate with bracket info."""
        try:
            import datetime as _dt

            invoices = self.query(Invoice)
            country = self._get_country()
            currency = self._get_tax_currency(country)
            spending = compute_spendable_income(invoices, country, currency=currency)
            tax_reserve = compute_income_tax_reserve(spending.net_revenue_ytd, country)

            days_elapsed = max(
                (_dt.date.today() - _dt.date.today().replace(month=1, day=1)).days, 1
            )
            annualized = float(spending.net_revenue_ytd) * 365 / days_elapsed

            try:
                tax_system = get_tax_system(country)
                bracket_data = self._compute_bracket_data(
                    tax_system, Decimal(str(annualized))
                )
                country_supported = True
            except NotImplementedError:
                bracket_data = []
                country_supported = False

            data = {
                "tax_reserve": tax_reserve,
                "annualized_income": Decimal(str(round(annualized, 2))),
                "brackets": bracket_data,
                "country": country,
                "country_supported": country_supported,
                "currency": currency,
            }
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to compute income tax estimate.",
                log_message=f"TaxIntent.get_income_tax_estimate: {e}",
                exception=e,
            )

    def _compute_bracket_data(self, tax_system, annualized_income: Decimal) -> list:
        """Build bracket visualization data from the tax system's zone data."""
        zones = tax_system.bracket_info
        income_f = float(annualized_income)
        allowance = tax_system.params.basic_allowance
        brackets = []
        prev_end = 0
        for zone in zones:
            up_to = zone["up_to"]
            ztype = zone.get("type")
            if ztype == "zero":
                start = 0
                end = up_to
            elif ztype in ("quadratic", "linear") and "reference_offset" in zone:
                # German-style zones with explicit reference offsets
                start = zone["reference_offset"]
                end = up_to if up_to is not None else start + 100000
            else:
                # Marginal bracket zones: display bracket range offset by allowance
                start = prev_end + allowance if not brackets else prev_end
                end = (up_to + allowance) if up_to is not None else start + 100000
            brackets.append(
                {
                    "label": zone["label"],
                    "start": start,
                    "end": end,
                    "is_current": start
                    <= income_f
                    < (end if up_to is not None else float("inf")),
                }
            )
            prev_end = end
        return brackets

    def get_quarterly_vat(self, year: int | None = None) -> IntentResult:
        """Get quarterly VAT breakdown."""
        try:
            invoices = self.query(Invoice)
            country = self._get_country()
            currency = self._get_tax_currency(country)
            quarters = quarterly_vat_breakdown(invoices, year=year, currency=currency)
            data = {"quarters": quarters, "currency": currency}
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to compute quarterly VAT.",
                log_message=f"TaxIntent.get_quarterly_vat: {e}",
                exception=e,
            )
