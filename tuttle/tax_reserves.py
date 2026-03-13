"""Tax reserve calculations for freelancers.

Computes how much of the freelancer's revenue must be set aside for
VAT payments and estimated income tax, yielding the actual spendable income.
"""

import datetime
import logging
from decimal import Decimal
from typing import List, NamedTuple, Optional

from .model import Invoice
from .tax import get_tax_system

logger = logging.getLogger(__name__)


class VATReserve(NamedTuple):
    """VAT collected that must be remitted to the tax authority."""

    vat_collected: Decimal  # total VAT on invoices in the period
    invoice_count: int  # number of invoices considered
    period_start: datetime.date
    period_end: datetime.date


class IncomeTaxReserve(NamedTuple):
    """Estimated income tax reserve for the current year."""

    estimated_annual_tax: Decimal  # full-year income tax estimate
    solidarity_surcharge: Decimal  # full-year soli estimate
    total_annual_reserve: Decimal  # tax + soli
    ytd_reserve: Decimal  # prorated to current date
    effective_rate: Decimal  # total_annual_reserve / annualized_income


class SpendableIncome(NamedTuple):
    """What the freelancer can actually spend."""

    gross_revenue_ytd: Decimal  # total invoiced amount (incl. VAT)
    net_revenue_ytd: Decimal  # gross minus VAT
    vat_reserve: Decimal  # VAT to set aside
    income_tax_reserve: Decimal  # estimated income tax + soli (prorated)
    spendable: Decimal  # net_revenue - income_tax_reserve


def _invoice_currency(inv: Invoice) -> Optional[str]:
    """Return the ISO 4217 currency code for an invoice, or None."""
    if inv.contract and inv.contract.currency:
        return inv.contract.currency
    return None


def compute_vat_reserves(
    invoices: List[Invoice],
    period_start: datetime.date,
    period_end: datetime.date,
    currency: Optional[str] = None,
) -> VATReserve:
    """Sum VAT collected on non-cancelled invoices in the given period.

    If *currency* is given, only invoices denominated in that currency are
    included; others are silently skipped (a debug log is emitted).
    """
    vat_total = Decimal(0)
    count = 0
    skipped = 0
    for inv in invoices:
        if inv.cancelled:
            continue
        if period_start <= inv.date <= period_end:
            if currency and _invoice_currency(inv) not in (currency, None):
                skipped += 1
                continue
            vat_total += inv.VAT_total
            count += 1
    if skipped:
        logger.debug(
            "compute_vat_reserves: skipped %d invoice(s) with currency != %s",
            skipped,
            currency,
        )
    return VATReserve(
        vat_collected=vat_total,
        invoice_count=count,
        period_start=period_start,
        period_end=period_end,
    )


def compute_income_tax_reserve(
    net_revenue_ytd: Decimal,
    country: str,
    deductions: Decimal = Decimal(0),
) -> IncomeTaxReserve:
    """Estimate income tax reserve based on year-to-date net revenue.

    Annualizes the YTD net revenue, computes the tax on that projected
    annual income, then prorates back to the current date.
    """
    today = datetime.date.today()
    try:
        tax_system = get_tax_system(country, date=today)
    except NotImplementedError:
        return IncomeTaxReserve(
            estimated_annual_tax=Decimal(0),
            solidarity_surcharge=Decimal(0),
            total_annual_reserve=Decimal(0),
            ytd_reserve=Decimal(0),
            effective_rate=Decimal(0),
        )
    year_start = today.replace(month=1, day=1)
    days_elapsed = max((today - year_start).days, 1)
    days_in_year = 365

    # Annualize: project YTD revenue to full year
    annualized_income = (net_revenue_ytd - deductions) * days_in_year / days_elapsed

    if annualized_income <= 0:
        return IncomeTaxReserve(
            estimated_annual_tax=Decimal(0),
            solidarity_surcharge=Decimal(0),
            total_annual_reserve=Decimal(0),
            ytd_reserve=Decimal(0),
            effective_rate=Decimal(0),
        )

    # Compute annual tax
    annual_tax = tax_system.income_tax(annualized_income)
    annual_soli = tax_system.solidarity_surcharge(annual_tax)
    total_annual = annual_tax + annual_soli

    # Prorate to current date
    ytd_reserve = (total_annual * days_elapsed / days_in_year).quantize(Decimal("0.01"))

    # Effective rate
    effective_rate = (
        (total_annual / annualized_income) if annualized_income > 0 else Decimal(0)
    )

    return IncomeTaxReserve(
        estimated_annual_tax=annual_tax,
        solidarity_surcharge=annual_soli,
        total_annual_reserve=total_annual,
        ytd_reserve=ytd_reserve,
        effective_rate=effective_rate.quantize(Decimal("0.0001")),
    )


def compute_spendable_income(
    invoices: List[Invoice],
    country: str,
    deductions: Decimal = Decimal(0),
    currency: Optional[str] = None,
) -> SpendableIncome:
    """Compute spendable income: what's left after VAT and income tax reserves.

    This answers the freelancer's core question: "How much of this money is mine?"

    If *currency* is given (the tax system's native currency), only invoices
    denominated in that currency are counted.  If not given, the currency is
    resolved automatically from the tax system for *country*.
    """
    today = datetime.date.today()
    year_start = today.replace(month=1, day=1)

    if currency is None:
        try:
            tax_system = get_tax_system(country, date=today)
            currency = tax_system.currency
        except NotImplementedError:
            pass

    gross_ytd = Decimal(0)
    vat_ytd = Decimal(0)
    skipped = 0

    for inv in invoices:
        if inv.cancelled:
            continue
        if inv.date >= year_start:
            if currency and _invoice_currency(inv) not in (currency, None):
                skipped += 1
                continue
            gross_ytd += inv.total
            vat_ytd += inv.VAT_total

    if skipped:
        logger.debug(
            "compute_spendable_income: skipped %d invoice(s) with currency != %s",
            skipped,
            currency,
        )

    net_ytd = gross_ytd - vat_ytd

    tax_reserve = compute_income_tax_reserve(net_ytd, country, deductions)

    spendable = net_ytd - tax_reserve.ytd_reserve

    return SpendableIncome(
        gross_revenue_ytd=gross_ytd,
        net_revenue_ytd=net_ytd,
        vat_reserve=vat_ytd,
        income_tax_reserve=tax_reserve.ytd_reserve,
        spendable=spendable,
    )


def quarterly_vat_breakdown(
    invoices: List[Invoice],
    year: Optional[int] = None,
    currency: Optional[str] = None,
) -> list:
    """VAT breakdown by quarter for the given year.

    Returns list of dicts: quarter, vat_collected, invoice_count, period_start, period_end.
    """
    if year is None:
        year = datetime.date.today().year

    quarters = []
    for q in range(1, 5):
        start_month = (q - 1) * 3 + 1
        end_month = q * 3
        period_start = datetime.date(year, start_month, 1)
        if end_month == 12:
            period_end = datetime.date(year, 12, 31)
        else:
            period_end = datetime.date(year, end_month + 1, 1) - datetime.timedelta(
                days=1
            )

        reserve = compute_vat_reserves(
            invoices, period_start, period_end, currency=currency
        )
        quarters.append(
            {
                "quarter": f"Q{q}",
                "vat_collected": reserve.vat_collected,
                "invoice_count": reserve.invoice_count,
                "period_start": period_start,
                "period_end": period_end,
            }
        )
    return quarters
