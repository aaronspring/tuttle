"""Business logic for the dashboard view."""


from ..core.abstractions import SQLModelDataSourceMixin, Intent
from ..core.intent_result import IntentResult

from ...model import Contract, Invoice, Project, FinancialGoal, User
from ...kpi import (
    compute_kpis,
    monthly_revenue_breakdown,
    monthly_spendable_breakdown,
    project_budget_status,
)
from ...forecasting import revenue_curve


class DashboardIntent(SQLModelDataSourceMixin, Intent):
    """Gathers data for the freelance business dashboard."""

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

    def get_kpis(self) -> IntentResult:
        """Compute KPI summary from all invoices, contracts, projects."""
        try:
            invoices = self.query(Invoice)
            contracts = self.query(Contract)
            projects = self.query(Project)
            country = self._get_country()
            kpis = compute_kpis(invoices, contracts, projects, country=country)
            return IntentResult(was_intent_successful=True, data=kpis)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to compute KPIs.",
                log_message=f"DashboardIntent.get_kpis: {e}",
                exception=e,
            )

    def get_monthly_revenue(self, n_months: int = 12) -> IntentResult:
        """Get monthly revenue breakdown for the last n months."""
        try:
            invoices = self.query(Invoice)
            data = monthly_revenue_breakdown(invoices, n_months=n_months)
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load monthly revenue.",
                log_message=f"DashboardIntent.get_monthly_revenue: {e}",
                exception=e,
            )

    def get_monthly_spendable_income(self, n_months: int = 12) -> IntentResult:
        """Get monthly spendable income breakdown for the last n months."""
        try:
            invoices = self.query(Invoice)
            country = self._get_country()
            data = monthly_spendable_breakdown(
                invoices,
                country=country,
                n_months=n_months,
            )
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load monthly spendable income.",
                log_message=f"DashboardIntent.get_monthly_spendable_income: {e}",
                exception=e,
            )

    def get_monthly_chart_data(self, n_months: int = 12) -> IntentResult:
        """Revenue + spendable in one query (avoids duplicate invoice loads)."""
        try:
            invoices = self.query(Invoice)
            country = self._get_country()
            revenue = monthly_revenue_breakdown(invoices, n_months=n_months)
            spendable = monthly_spendable_breakdown(
                invoices, country=country, n_months=n_months
            )
            return IntentResult(
                was_intent_successful=True,
                data={"revenue": revenue, "spendable": spendable},
            )
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load chart data.",
                log_message=f"DashboardIntent.get_monthly_chart_data: {e}",
                exception=e,
            )

    def get_revenue_curve(self, forecast_months: int = 6) -> IntentResult:
        """Get combined historical + forecast revenue curve."""
        try:
            invoices = self.query(Invoice)
            contracts = self.query(Contract)
            data = revenue_curve(invoices, contracts, forecast_months=forecast_months)
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to generate revenue forecast.",
                log_message=f"DashboardIntent.get_revenue_curve: {e}",
                exception=e,
            )

    def get_project_budgets(self) -> IntentResult:
        """Get budget utilization for all projects."""
        try:
            projects = self.query(Project)
            data = project_budget_status(projects)
            return IntentResult(was_intent_successful=True, data=data)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load project budgets.",
                log_message=f"DashboardIntent.get_project_budgets: {e}",
                exception=e,
            )

    def get_financial_goals(self) -> IntentResult:
        """Load all financial goals."""
        try:
            goals = self.query(FinancialGoal)
            return IntentResult(was_intent_successful=True, data=goals)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to load financial goals.",
                log_message=f"DashboardIntent.get_financial_goals: {e}",
                exception=e,
            )

    def save_financial_goal(self, goal: FinancialGoal) -> IntentResult:
        """Save a financial goal."""
        try:
            self.store(goal)
            return IntentResult(was_intent_successful=True, data=goal)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to save financial goal.",
                log_message=f"DashboardIntent.save_financial_goal: {e}",
                exception=e,
            )

    def delete_financial_goal(self, goal_id: int) -> IntentResult:
        """Delete a financial goal by ID."""
        try:
            self.delete_by_id(FinancialGoal, goal_id)
            return IntentResult(was_intent_successful=True, data=None)
        except Exception as e:
            return IntentResult(
                was_intent_successful=False,
                error_msg="Failed to delete financial goal.",
                log_message=f"DashboardIntent.delete_financial_goal: {e}",
                exception=e,
            )
