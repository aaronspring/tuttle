"""Key Performance Indicators for freelance business analysis."""

import datetime
from decimal import Decimal
from typing import List, Optional, NamedTuple

from .model import Contract, Invoice, Project, User
from .tax import get_tax_system
from .tax_reserves import compute_spendable_income


class KPISummary(NamedTuple):
    """Snapshot of key business metrics."""

    total_revenue: Decimal
    total_revenue_ytd: Decimal
    outstanding_amount: Decimal
    overdue_amount: Decimal
    effective_hourly_rate: Optional[Decimal]
    utilization_rate: Optional[float]
    active_projects: int
    active_contracts: int
    unpaid_invoices: int
    overdue_invoices: int
    # Tax reserves
    vat_reserve: Decimal
    income_tax_reserve: Decimal
    spendable_income: Decimal
    tax_currency: str = "EUR"


def compute_kpis(
    invoices: List[Invoice],
    contracts: List[Contract],
    projects: List[Project],
    country: str = "Germany",
) -> KPISummary:
    """Compute business KPIs from current data."""
    today = datetime.date.today()
    year_start = today.replace(month=1, day=1)

    # Revenue metrics
    total_revenue = Decimal(0)
    total_revenue_ytd = Decimal(0)
    outstanding_amount = Decimal(0)
    overdue_amount = Decimal(0)
    unpaid_invoices = 0
    overdue_invoices = 0
    total_hours = Decimal(0)
    paid_revenue = Decimal(0)

    for inv in invoices:
        if inv.cancelled:
            continue
        inv_total = inv.total

        if inv.paid:
            total_revenue += inv_total
            if inv.date >= year_start:
                total_revenue_ytd += inv_total
            # Accumulate hours for effective rate calculation
            for ts in inv.timesheets:
                for item in ts.items:
                    hours = item.duration.total_seconds() / 3600
                    total_hours += Decimal(str(hours))
            paid_revenue += inv_total
        else:
            outstanding_amount += inv_total
            unpaid_invoices += 1
            if inv.due_date and inv.due_date < today:
                overdue_amount += inv_total
                overdue_invoices += 1

    # Effective hourly rate: paid revenue / total tracked hours
    effective_hourly_rate = None
    if total_hours > 0:
        effective_hourly_rate = paid_revenue / total_hours

    # Active contracts / projects
    active_contracts = sum(1 for c in contracts if c.is_active())
    active_projects = sum(1 for p in projects if p.is_active())

    # Utilization rate: tracked hours / available hours (based on workdays)
    utilization_rate = None
    if active_contracts:
        # Available hours since year start
        days_elapsed = (today - year_start).days or 1
        workdays_elapsed = int(days_elapsed * 5 / 7)
        # Sum contracted hours per workday across active contracts
        available_hours_per_day = sum(
            c.units_per_workday for c in contracts if c.is_active()
        )
        available_hours = Decimal(str(workdays_elapsed * available_hours_per_day))
        if available_hours > 0:
            utilization_rate = float(total_hours / available_hours)

    # Tax reserves — resolve currency from the tax system
    tax_currency = "EUR"
    try:
        tax_system = get_tax_system(country)
        tax_currency = tax_system.currency
    except NotImplementedError:
        pass

    try:
        spending = compute_spendable_income(invoices, country, currency=tax_currency)
        vat_reserve = spending.vat_reserve
        income_tax_reserve = spending.income_tax_reserve
        spendable_income = spending.spendable
    except NotImplementedError:
        vat_reserve = Decimal(0)
        income_tax_reserve = Decimal(0)
        spendable_income = Decimal(0)

    return KPISummary(
        total_revenue=total_revenue,
        total_revenue_ytd=total_revenue_ytd,
        outstanding_amount=outstanding_amount,
        overdue_amount=overdue_amount,
        effective_hourly_rate=effective_hourly_rate,
        utilization_rate=utilization_rate,
        active_projects=active_projects,
        active_contracts=active_contracts,
        unpaid_invoices=unpaid_invoices,
        overdue_invoices=overdue_invoices,
        vat_reserve=vat_reserve,
        income_tax_reserve=income_tax_reserve,
        spendable_income=spendable_income,
        tax_currency=tax_currency,
    )


def monthly_revenue_breakdown(
    invoices: List[Invoice],
    n_months: int = 12,
) -> list:
    """Revenue breakdown by month for the last n_months.

    Returns a list of dicts with keys: month, revenue, invoice_count.
    """
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30 * n_months)).replace(day=1)

    months = {}
    current = start
    while current <= today:
        key = current.strftime("%Y-%m")
        months[key] = {"month": key, "revenue": Decimal(0), "invoice_count": 0}
        current = (current + datetime.timedelta(days=32)).replace(day=1)

    for inv in invoices:
        if inv.cancelled:
            continue
        key = inv.date.strftime("%Y-%m")
        if key in months:
            months[key]["revenue"] += inv.total
            months[key]["invoice_count"] += 1

    return sorted(months.values(), key=lambda x: x["month"])


def monthly_spendable_breakdown(
    invoices: List[Invoice],
    country: str = "Germany",
    n_months: int = 12,
    deductions: Decimal = Decimal(0),
) -> list:
    """Estimate monthly spendable income after VAT and income-tax true-up.

    For each month bucket this returns:
    - gross_revenue: invoiced amount including VAT
    - vat_due: VAT to reserve for that month
    - net_revenue: gross_revenue - vat_due
    - income_tax_true_up: monthly delta in YTD tax reserve estimate
    - spendable: net_revenue - income_tax_true_up
    """
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30 * n_months)).replace(day=1)

    months = {}
    current = start
    while current <= today:
        key = current.strftime("%Y-%m")
        months[key] = {
            "month": key,
            "gross_revenue": Decimal(0),
            "vat_due": Decimal(0),
            "net_revenue": Decimal(0),
            "income_tax_true_up": Decimal(0),
            "spendable": Decimal(0),
            "invoice_count": 0,
        }
        current = (current + datetime.timedelta(days=32)).replace(day=1)

    # Resolve currency from the tax system. Non-matching invoice currencies are
    # skipped to avoid mixing values in the spendable estimate.
    currency = None
    try:
        currency = get_tax_system(country).currency
    except NotImplementedError:
        pass

    for inv in invoices:
        if inv.cancelled:
            continue
        if currency and inv.contract and inv.contract.currency not in (currency, None):
            continue
        key = inv.date.strftime("%Y-%m")
        if key in months:
            months[key]["gross_revenue"] += inv.total
            months[key]["vat_due"] += inv.VAT_total
            months[key]["invoice_count"] += 1

    sorted_keys = sorted(months.keys())
    cumulative_net_ytd = Decimal(0)
    previous_ytd_reserve = Decimal(0)

    for key in sorted_keys:
        m = months[key]
        m["net_revenue"] = m["gross_revenue"] - m["vat_due"]
        year, month = key.split("-")
        month_start = datetime.date(int(year), int(month), 1)
        if month_start.year == today.year:
            cumulative_net_ytd += m["net_revenue"]
            month_end = (month_start + datetime.timedelta(days=32)).replace(
                day=1
            ) - datetime.timedelta(days=1)
            as_of = min(month_end, today)
            year_start = as_of.replace(month=1, day=1)
            days_elapsed = max((as_of - year_start).days, 1)
            days_in_year = 365

            annualized_income = (
                (cumulative_net_ytd - deductions) * days_in_year / days_elapsed
            )
            if annualized_income <= 0:
                ytd_reserve = Decimal(0)
            else:
                try:
                    tax_system = get_tax_system(country, date=as_of)
                    annual_tax = tax_system.income_tax(annualized_income)
                    annual_soli = tax_system.solidarity_surcharge(annual_tax)
                    total_annual = annual_tax + annual_soli
                    ytd_reserve = (total_annual * days_elapsed / days_in_year).quantize(
                        Decimal("0.01")
                    )
                except NotImplementedError:
                    ytd_reserve = Decimal(0)

            m["income_tax_true_up"] = ytd_reserve - previous_ytd_reserve
            previous_ytd_reserve = ytd_reserve
        else:
            # Keep non-current-year months neutral so the chart remains stable
            # when showing a rolling window that crosses year boundaries.
            m["income_tax_true_up"] = Decimal(0)

        m["spendable"] = m["net_revenue"] - m["income_tax_true_up"]

    return [months[k] for k in sorted_keys]


def project_budget_status(
    projects: List[Project],
) -> list:
    """Budget utilization for each project with timesheets.

    Returns a list of dicts with keys: project, hours_tracked, hours_budget, progress.
    """
    results = []
    for project in projects:
        if not project.contract or not project.contract.volume:
            continue
        hours_tracked = Decimal(0)
        for ts in project.timesheets:
            for item in ts.items:
                hours_tracked += Decimal(str(item.duration.total_seconds() / 3600))
        hours_budget = Decimal(str(project.contract.volume))
        progress = float(hours_tracked / hours_budget) if hours_budget > 0 else 0.0

        results.append(
            {
                "project": project.title,
                "hours_tracked": float(hours_tracked),
                "hours_budget": float(hours_budget),
                "progress": min(progress, 1.0),
            }
        )
    return results
