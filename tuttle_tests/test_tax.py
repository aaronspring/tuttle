"""Tests for data-driven tax system and tax reserve calculations."""

import datetime
from decimal import Decimal

import pytest

from tuttle import tax
from tuttle.tax import TaxSystem, get_tax_system, supported_countries, available_years
from tuttle.tax_reserves import (
    compute_income_tax_reserve,
    compute_spendable_income,
    compute_vat_reserves,
    quarterly_vat_breakdown,
)
from tuttle.kpi import monthly_spendable_breakdown
from tuttle.model import (
    Address,
    Client,
    Contact,
    Contract,
    Invoice,
    InvoiceItem,
    Project,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def german_tax():
    """Current-year German tax system."""
    return get_tax_system("Germany")


@pytest.fixture
def german_tax_2024():
    return get_tax_system("Germany", date=datetime.date(2024, 6, 1))


@pytest.fixture
def german_tax_2025():
    return get_tax_system("Germany", date=datetime.date(2025, 6, 1))


@pytest.fixture
def german_tax_2026():
    return get_tax_system("Germany", date=datetime.date(2026, 6, 1))


def _make_invoice(date, items_data, cancelled=False):
    """Create a minimal Invoice with InvoiceItems for testing.

    items_data: list of (quantity, unit_price, vat_rate) tuples.
    """
    contact = Contact(name="Test Contact", email="test@example.com")
    client = Client(name="Test Client", invoicing_contact=contact)
    contract = Contract(
        title="Test Contract",
        client=client,
        rate=Decimal("100"),
        currency="EUR",
        unit="hour",
        units_per_workday=8,
        term_of_payment=30,
        VAT_rate=Decimal("0.19"),
    )
    project = Project(title="Test Project", tag="test", contract=contract)
    invoice = Invoice(
        number=f"INV-{date.isoformat()}",
        date=date,
        contract=contract,
        project=project,
        cancelled=cancelled,
        sent=True,
        paid=True,
    )
    for qty, price, vat_rate in items_data:
        InvoiceItem(
            invoice=invoice,
            start_date=date,
            end_date=date,
            quantity=qty,
            unit="hour",
            unit_price=Decimal(str(price)),
            VAT_rate=Decimal(str(vat_rate)),
            description="Test item",
        )
    return invoice


# ── TaxSystem framework ──────────────────────────────────────


class TestTaxSystemFramework:
    def test_get_tax_system_germany(self):
        system = get_tax_system("Germany")
        assert isinstance(system, TaxSystem)
        assert system.country == "Germany"

    def test_get_tax_system_deutschland(self):
        system = get_tax_system("Deutschland")
        assert isinstance(system, TaxSystem)
        assert system.country == "Germany"

    def test_get_tax_system_unsupported(self):
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            get_tax_system("Narnia")

    def test_supported_countries(self):
        countries = supported_countries()
        assert "Germany" in countries

    def test_available_years(self):
        years = available_years("Germany")
        assert 2024 in years
        assert 2025 in years
        assert 2026 in years

    def test_year_selection(self):
        """Different dates yield different year parameters."""
        sys_2024 = get_tax_system("Germany", date=datetime.date(2024, 7, 1))
        sys_2026 = get_tax_system("Germany", date=datetime.date(2026, 7, 1))
        assert sys_2024.year == 2024
        assert sys_2026.year == 2026
        # Basic allowance increased 2024 → 2026
        assert sys_2024.params.basic_allowance < sys_2026.params.basic_allowance

    def test_year_fallback(self):
        """Year without data falls back to nearest available."""
        sys = get_tax_system("Germany", date=datetime.date(2030, 1, 1))
        # Should get the latest available year
        assert sys.year == max(available_years("Germany"))


# ── German income tax ────────────────────────────────────────


class TestGermanIncomeTax:
    def test_zero_income(self, german_tax):
        assert german_tax.income_tax(Decimal(0)) == 0

    def test_below_basic_allowance(self, german_tax_2026):
        """Income below basic allowance (12,096€ for 2026) → 0 tax."""
        assert german_tax_2026.income_tax(Decimal("10000")) == 0
        assert german_tax_2026.income_tax(Decimal("12096")) == 0

    def test_just_above_basic_allowance(self, german_tax):
        """Income just above basic allowance → small tax."""
        allowance = german_tax.params.basic_allowance
        tax_amount = german_tax.income_tax(Decimal(str(allowance + 200)))
        assert tax_amount > 0
        assert tax_amount < 100

    def test_zone2(self, german_tax):
        """Income in zone 2 → moderate tax."""
        tax_amount = german_tax.income_tax(Decimal("15000"))
        assert tax_amount > 0
        assert tax_amount < 2000

    def test_zone3(self, german_tax):
        """Income in zone 3 → progressive tax."""
        tax_amount = german_tax.income_tax(Decimal("50000"))
        assert 10000 < tax_amount < 15000

    def test_zone4(self, german_tax):
        """Income in zone 4 → 42% marginal rate."""
        tax_amount = german_tax.income_tax(Decimal("100000"))
        assert 25000 < tax_amount < 35000

    def test_zone5(self, german_tax):
        """Income above top threshold → 45% marginal rate."""
        tax_amount = german_tax.income_tax(Decimal("300000"))
        assert tax_amount > 100000

    def test_progressive_nature(self, german_tax):
        """Higher income → higher effective rate."""
        rate_30k = german_tax.income_tax(Decimal("30000")) / 30000
        rate_80k = german_tax.income_tax(Decimal("80000")) / 80000
        rate_200k = german_tax.income_tax(Decimal("200000")) / 200000
        assert rate_30k < rate_80k < rate_200k

    def test_backward_compat_function(self):
        """Legacy income_tax() and income_tax_germany() still work."""
        amount1 = tax.income_tax(Decimal("50000"), "Germany")
        amount2 = tax.income_tax_germany(Decimal("50000"))
        assert amount1 == amount2

    def test_different_years_different_tax(self):
        """Tax for same income should differ between years due to allowance changes."""
        income = Decimal("40000")
        tax_2024 = get_tax_system("Germany", datetime.date(2024, 1, 1)).income_tax(
            income
        )
        tax_2026 = get_tax_system("Germany", datetime.date(2026, 1, 1)).income_tax(
            income
        )
        # Higher basic allowance in 2026 means slightly less tax
        assert tax_2026 < tax_2024


# ── Solidarity surcharge ──────────────────────────────────────


class TestSolidaritySurcharge:
    def test_zero_tax(self, german_tax):
        assert german_tax.solidarity_surcharge(Decimal(0)) == 0

    def test_standard_case(self, german_tax):
        tax_amount = Decimal("10000")
        soli = german_tax.solidarity_surcharge(tax_amount)
        assert soli == Decimal("550.00")

    def test_total_tax(self, german_tax):
        """total_tax = income_tax + soli."""
        income = Decimal("50000")
        it = german_tax.income_tax(income)
        soli = german_tax.solidarity_surcharge(it)
        total = german_tax.total_tax(income)
        assert total == it + soli


# ── VAT ───────────────────────────────────────────────────────


class TestGermanVAT:
    def test_standard_rate(self, german_tax):
        assert german_tax.vat_rate_standard() == Decimal("0.19")

    def test_reduced_rate(self, german_tax):
        assert german_tax.vat_rate_reduced() == Decimal("0.07")


# ── VAT reserves ──────────────────────────────────────────────


class TestVATReserves:
    def test_basic_vat_reserve(self):
        invoices = [
            _make_invoice(datetime.date(2026, 1, 15), [(10, 100, 0.19)]),
            _make_invoice(datetime.date(2026, 2, 15), [(5, 200, 0.19)]),
        ]
        result = compute_vat_reserves(
            invoices,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 3, 31),
        )
        assert result.vat_collected > 0
        assert result.invoice_count == 2

    def test_excludes_cancelled(self):
        invoices = [
            _make_invoice(datetime.date(2026, 1, 15), [(10, 100, 0.19)]),
            _make_invoice(datetime.date(2026, 2, 15), [(5, 200, 0.19)], cancelled=True),
        ]
        result = compute_vat_reserves(
            invoices,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 3, 31),
        )
        assert result.invoice_count == 1

    def test_excludes_out_of_period(self):
        invoices = [
            _make_invoice(datetime.date(2025, 12, 15), [(10, 100, 0.19)]),
            _make_invoice(datetime.date(2026, 1, 15), [(5, 200, 0.19)]),
        ]
        result = compute_vat_reserves(
            invoices,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 3, 31),
        )
        assert result.invoice_count == 1

    def test_empty_invoices(self):
        result = compute_vat_reserves(
            [], datetime.date(2026, 1, 1), datetime.date(2026, 3, 31)
        )
        assert result.vat_collected == Decimal(0)
        assert result.invoice_count == 0


# ── Income tax reserve ────────────────────────────────────────


class TestIncomeTaxReserve:
    def test_basic_reserve(self):
        result = compute_income_tax_reserve(Decimal("40000"), "Germany")
        assert result.estimated_annual_tax > 0
        assert result.solidarity_surcharge > 0
        assert result.total_annual_reserve > result.estimated_annual_tax
        assert result.ytd_reserve > 0
        assert 0 < result.effective_rate < 1

    def test_zero_revenue(self):
        result = compute_income_tax_reserve(Decimal(0), "Germany")
        assert result.estimated_annual_tax == 0
        assert result.ytd_reserve == 0

    def test_negative_revenue(self):
        result = compute_income_tax_reserve(Decimal("-5000"), "Germany")
        assert result.estimated_annual_tax == 0

    def test_ytd_is_prorated(self):
        """YTD reserve should be less than annual reserve."""
        result = compute_income_tax_reserve(Decimal("50000"), "Germany")
        assert result.ytd_reserve <= result.total_annual_reserve


# ── Spendable income ──────────────────────────────────────────


class TestSpendableIncome:
    def test_basic_spendable(self):
        today = datetime.date.today()
        invoices = [
            _make_invoice(today.replace(day=1), [(100, 100, 0.19)]),
        ]
        result = compute_spendable_income(invoices, "Germany")
        assert result.gross_revenue_ytd > 0
        assert result.vat_reserve > 0
        assert result.net_revenue_ytd == result.gross_revenue_ytd - result.vat_reserve
        assert result.spendable < result.net_revenue_ytd
        assert result.spendable == result.net_revenue_ytd - result.income_tax_reserve

    def test_spendable_excludes_cancelled(self):
        today = datetime.date.today()
        invoices = [
            _make_invoice(today.replace(day=1), [(100, 100, 0.19)]),
            _make_invoice(today.replace(day=1), [(50, 100, 0.19)], cancelled=True),
        ]
        result = compute_spendable_income(invoices, "Germany")
        # Only the non-cancelled invoice should count
        expected_gross = invoices[0].total
        assert result.gross_revenue_ytd == expected_gross

    def test_spendable_excludes_previous_year(self):
        today = datetime.date.today()
        invoices = [
            _make_invoice(datetime.date(today.year - 1, 6, 1), [(100, 100, 0.19)]),
            _make_invoice(today.replace(day=1), [(50, 100, 0.19)]),
        ]
        result = compute_spendable_income(invoices, "Germany")
        # Only this year's invoice should count
        assert result.gross_revenue_ytd == invoices[1].total

    def test_monthly_spendable_breakdown_includes_vat_subtraction(self):
        today = datetime.date.today()
        invoices = [
            _make_invoice(today.replace(day=1), [(20, 100, 0.19)]),
        ]
        monthly = monthly_spendable_breakdown(invoices, country="Germany", n_months=2)
        this_month = [m for m in monthly if m["month"] == today.strftime("%Y-%m")][0]
        assert this_month["gross_revenue"] > 0
        assert this_month["vat_due"] > 0
        assert (
            this_month["net_revenue"]
            == this_month["gross_revenue"] - this_month["vat_due"]
        )
        assert (
            this_month["spendable"]
            == this_month["net_revenue"] - this_month["income_tax_true_up"]
        )


# ── Quarterly VAT breakdown ──────────────────────────────────


class TestQuarterlyVAT:
    def test_four_quarters(self):
        invoices = [
            _make_invoice(datetime.date(2026, 1, 15), [(10, 100, 0.19)]),
            _make_invoice(datetime.date(2026, 5, 15), [(20, 100, 0.19)]),
            _make_invoice(datetime.date(2026, 9, 15), [(30, 100, 0.19)]),
        ]
        result = quarterly_vat_breakdown(invoices, year=2026)
        assert len(result) == 4
        assert result[0]["quarter"] == "Q1"
        assert result[0]["invoice_count"] == 1
        assert result[1]["quarter"] == "Q2"
        assert result[1]["invoice_count"] == 1
        assert result[2]["quarter"] == "Q3"
        assert result[2]["invoice_count"] == 1
        assert result[3]["quarter"] == "Q4"
        assert result[3]["invoice_count"] == 0

    def test_defaults_to_current_year(self):
        result = quarterly_vat_breakdown([], year=None)
        assert len(result) == 4
        assert result[0]["period_start"].year == datetime.date.today().year


# ── Spanish tax system (validates marginal_brackets formula) ──


@pytest.fixture
def spanish_tax():
    """Current-year Spanish tax system."""
    return get_tax_system("Spain")


class TestSpanishTaxSystem:
    def test_get_tax_system_spain(self):
        system = get_tax_system("Spain")
        assert isinstance(system, TaxSystem)
        assert system.country == "Spain"

    def test_get_tax_system_espana_alias(self):
        system = get_tax_system("España")
        assert system.country == "Spain"

    def test_available_years_spain(self):
        years = available_years("Spain")
        assert 2024 in years
        assert 2025 in years
        assert 2026 in years

    def test_supported_countries_includes_spain(self):
        countries = supported_countries()
        assert "Spain" in countries
        assert "Germany" in countries


class TestSpanishIncomeTax:
    def test_zero_income(self, spanish_tax):
        assert spanish_tax.income_tax(Decimal(0)) == 0

    def test_below_personal_allowance(self, spanish_tax):
        """Income below mínimo personal (5,550€) → 0 tax."""
        assert spanish_tax.income_tax(Decimal("5000")) == 0
        assert spanish_tax.income_tax(Decimal("5550")) == 0

    def test_first_bracket(self, spanish_tax):
        """Income in first bracket (19% on income above 5,550€ up to 12,450+5,550)."""
        # 10,000€ income → 4,450€ taxable at 19% = 845.50 → rounds to 846
        tax_amount = spanish_tax.income_tax(Decimal("10000"))
        assert tax_amount > 0
        assert tax_amount < 1000

    def test_manual_calculation_20000(self, spanish_tax):
        """Manual check: 20,000€ income, personal allowance 5,550€.
        Taxable = 14,450€
        First 12,450€ at 19% = 2,365.50
        Next 2,000€ at 24% = 480.00
        Total = 2,845.50 → 2846
        """
        tax_amount = spanish_tax.income_tax(Decimal("20000"))
        assert 2800 < tax_amount < 2900

    def test_manual_calculation_50000(self, spanish_tax):
        """Manual check: 50,000€ income, personal allowance 5,550€.
        Taxable = 44,450€
        First 12,450€ at 19% = 2,365.50
        Next 7,750€ (20,200-12,450) at 24% = 1,860.00
        Next 15,000€ (35,200-20,200) at 30% = 4,500.00
        Next 9,250€ (44,450-35,200) at 37% = 3,422.50
        Total = 12,148.00 → 12148
        """
        tax_amount = spanish_tax.income_tax(Decimal("50000"))
        assert 12100 < tax_amount < 12200

    def test_top_bracket(self, spanish_tax):
        """Very high income hits the 47% top marginal rate."""
        tax_amount = spanish_tax.income_tax(Decimal("500000"))
        assert tax_amount > 200000

    def test_progressive_nature(self, spanish_tax):
        """Higher income → higher effective rate."""
        rate_20k = spanish_tax.income_tax(Decimal("20000")) / 20000
        rate_60k = spanish_tax.income_tax(Decimal("60000")) / 60000
        rate_200k = spanish_tax.income_tax(Decimal("200000")) / 200000
        assert rate_20k < rate_60k < rate_200k

    def test_no_solidarity_surcharge(self, spanish_tax):
        """Spain has no solidarity surcharge."""
        tax_amount = spanish_tax.income_tax(Decimal("50000"))
        soli = spanish_tax.solidarity_surcharge(tax_amount)
        assert soli == 0
        # total_tax equals income_tax for Spain
        assert spanish_tax.total_tax(Decimal("50000")) == tax_amount


class TestSpanishVAT:
    def test_standard_rate(self, spanish_tax):
        assert spanish_tax.vat_rate_standard() == Decimal("0.21")

    def test_reduced_rate(self, spanish_tax):
        assert spanish_tax.vat_rate_reduced() == Decimal("0.10")


class TestSpanishReserves:
    def test_income_tax_reserve_spain(self):
        result = compute_income_tax_reserve(Decimal("30000"), "Spain")
        assert result.estimated_annual_tax > 0
        assert result.solidarity_surcharge == 0
        assert result.total_annual_reserve == result.estimated_annual_tax
        assert 0 < result.effective_rate < 1

    def test_spendable_income_spain(self):
        today = datetime.date.today()
        invoices = [
            _make_invoice(today.replace(day=1), [(80, 100, 0.21)]),
        ]
        result = compute_spendable_income(invoices, "Spain")
        assert result.gross_revenue_ytd > 0
        assert result.vat_reserve > 0
        assert result.spendable < result.net_revenue_ytd


class TestCrossCountryComparison:
    def test_different_tax_for_same_income(self):
        """Germany and Spain produce different tax for the same income."""
        income = Decimal("50000")
        german = get_tax_system("Germany").income_tax(income)
        spanish = get_tax_system("Spain").income_tax(income)
        # Both should be positive but different
        assert german > 0
        assert spanish > 0
        assert german != spanish

    def test_different_vat_rates(self):
        """Germany 19% vs Spain 21%."""
        german = get_tax_system("Germany")
        spanish = get_tax_system("Spain")
        assert german.vat_rate_standard() < spanish.vat_rate_standard()
