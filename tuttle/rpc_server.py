"""JSON-RPC 2.0 server over stdio.

Bridges the existing intent layer to any external process (Electron, CLI, etc.)
by reading newline-delimited JSON-RPC requests from stdin and writing responses
to stdout.  Each request is dispatched to the appropriate intent method, and
SQLModel results are serialised via ``model_dump()``.

Usage::

    python -m tuttle.rpc_server
"""

import datetime
import json
import sys
import traceback
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Redirect loguru to stderr so it never pollutes the JSON-RPC stdout channel.
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# ---------------------------------------------------------------------------
# Lazy intent singletons
# ---------------------------------------------------------------------------

_intents: Dict[str, Any] = {}


def _get_intent(name: str):
    if name not in _intents:
        if name == "contacts":
            from tuttle.app.contacts.intent import ContactsIntent

            _intents[name] = ContactsIntent()
        elif name == "clients":
            from tuttle.app.clients.intent import ClientsIntent

            _intents[name] = ClientsIntent()
        elif name == "contracts":
            from tuttle.app.contracts.intent import ContractsIntent

            _intents[name] = ContractsIntent()
        elif name == "projects":
            from tuttle.app.projects.intent import ProjectsIntent

            _intents[name] = ProjectsIntent()
        elif name == "invoicing":
            from tuttle.app.invoicing.intent import InvoicingIntent

            _intents[name] = InvoicingIntent(client_storage=None)
        elif name == "invoicing_ds":
            from tuttle.app.invoicing.data_source import InvoicingDataSource

            _intents[name] = InvoicingDataSource()
        elif name == "dashboard":
            from tuttle.app.dashboard.intent import DashboardIntent

            _intents[name] = DashboardIntent()
        elif name == "timeline":
            from tuttle.app.timeline.intent import TimelineIntent

            _intents[name] = TimelineIntent()
        else:
            raise ValueError(f"Unknown intent domain: {name}")
    return _intents[name]


def _reset_intents():
    """Re-create all intent singletons (e.g. after demo data install)."""
    _intents.clear()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise(obj: Any) -> Any:
    """Recursively convert a Python value to JSON-safe primitives."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, datetime.timedelta):
        return obj.total_seconds()
    if isinstance(obj, dict):
        return {str(k): _serialise(v) for k, v in obj.items()}
    if hasattr(obj, "_asdict"):
        return _serialise(obj._asdict())
    if isinstance(obj, list):
        return [_serialise(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _serialise(obj.model_dump())
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses

        return _serialise(dataclasses.asdict(obj))
    if hasattr(obj, "value"):
        return _serialise(obj.value)
    return str(obj)


def _unwrap_intent_result(result) -> Dict[str, Any]:
    """Convert an IntentResult to a plain dict for JSON-RPC response."""
    return {
        "ok": result.was_intent_successful,
        "data": _serialise(result.data),
        "error": result.error_msg or None,
    }


# ---------------------------------------------------------------------------
# Method dispatch table
# ---------------------------------------------------------------------------


def _ensure_db():
    """Ensure the database exists and migrations are up to date."""
    from tuttle.app.core.database_storage_impl import DatabaseStorageImpl

    db = DatabaseStorageImpl(
        store_demo_timetracking_dataframe=lambda _: None,
        debug_mode=False,
    )
    db.ensure_database()


def _dispatch(method: str, params: Dict[str, Any]) -> Any:
    """Dispatch a JSON-RPC method string to the appropriate intent call."""

    # -- Contacts -----------------------------------------------------------
    if method == "contacts.get_all":
        result = _get_intent("contacts").get_all()
        if result.was_intent_successful and result.data:
            enriched = []
            for c in result.data:
                d = _serialise(c)
                if c.address:
                    d["address"] = _serialise(c.address)
                enriched.append(d)
            return {"ok": True, "data": enriched, "error": None}
        return _unwrap_intent_result(result)
    if method == "contacts.get_by_id":
        result = _get_intent("contacts").get_by_id(params["id"])
        if result.was_intent_successful and result.data:
            d = _serialise(result.data)
            if result.data.address:
                d["address"] = _serialise(result.data.address)
            return {"ok": True, "data": d, "error": None}
        return _unwrap_intent_result(result)
    if method == "contacts.save":
        from tuttle.model import Contact, Address

        data = params["contact"]
        addr_data = data.pop("address", {}) or {}
        intent = _get_intent("contacts")
        contact_id = data.get("id")
        if contact_id:
            existing = intent.get_by_id(contact_id)
            if not existing.was_intent_successful or not existing.data:
                return {"ok": False, "data": None, "error": "Contact not found"}
            contact = existing.data
            for k, v in data.items():
                if not k.startswith("_") and k not in (
                    "id",
                    "invoicing_contact_of",
                    "address",
                ):
                    setattr(contact, k, v)
            if contact.address:
                for k, v in addr_data.items():
                    if not k.startswith("_") and k != "id":
                        setattr(contact.address, k, v)
            elif addr_data:
                address = Address(
                    **{
                        k: v
                        for k, v in addr_data.items()
                        if k != "id" and not k.startswith("_")
                    }
                )
                contact.address = address
        else:
            address = Address(
                **{
                    k: v
                    for k, v in addr_data.items()
                    if k != "id" and not k.startswith("_")
                }
            )
            contact = Contact(
                address=address,
                **{
                    k: v
                    for k, v in data.items()
                    if not k.startswith("_") and k not in ("invoicing_contact_of",)
                },
            )
        return _unwrap_intent_result(intent.save_contact(contact))
    if method == "contacts.delete":
        return _unwrap_intent_result(
            _get_intent("contacts").delete_contact(params["id"])
        )

    # -- Clients ------------------------------------------------------------
    if method == "clients.get_all":
        return _unwrap_intent_result(_get_intent("clients").get_all())
    if method == "clients.get_all_contacts":
        contacts_map = _get_intent("clients").get_all_contacts_as_map()
        return {"ok": True, "data": _serialise(contacts_map), "error": None}
    if method == "clients.save":
        from tuttle.model import Client, Contact, Address

        data = params["client"]
        contact_data = data.pop("invoicing_contact", {}) or {}
        addr_data = contact_data.pop("address", {}) or {}
        address = Address(
            **{
                k: v
                for k, v in addr_data.items()
                if k != "id" and not k.startswith("_")
            }
        )
        if addr_data.get("id"):
            address.id = addr_data["id"]
        contact = Contact(
            address=address,
            **{
                k: v
                for k, v in contact_data.items()
                if not k.startswith("_") and k not in ("invoicing_contact_of",)
            },
        )
        if contact_data.get("id"):
            contact.id = contact_data["id"]
        client = Client(
            invoicing_contact=contact,
            **{
                k: v
                for k, v in data.items()
                if not k.startswith("_") and k not in ("contracts",)
            },
        )
        return _unwrap_intent_result(_get_intent("clients").save_client(client))
    if method == "clients.delete":
        return _unwrap_intent_result(_get_intent("clients").delete(params["id"]))

    # -- Contracts ----------------------------------------------------------
    if method == "contracts.get_all":
        return _unwrap_intent_result(_get_intent("contracts").get_all())
    if method == "contracts.get_all_clients":
        clients_map = _get_intent("contracts").get_all_clients_as_map()
        return {"ok": True, "data": _serialise(clients_map), "error": None}
    if method == "contracts.get_default_currency":
        return _unwrap_intent_result(_get_intent("contracts").get_default_currency())
    if method == "contracts.save":
        from tuttle.model import Contract

        data = params["contract"]
        client_id = data.get("client_id")
        clean = {
            k: v
            for k, v in data.items()
            if not k.startswith("_") and k not in ("client", "projects", "invoices")
        }
        contract = Contract(**clean)
        return _unwrap_intent_result(_get_intent("contracts").save_contract(contract))
    if method == "contracts.delete":
        return _unwrap_intent_result(_get_intent("contracts").delete(params["id"]))
    if method == "contracts.toggle_completed":
        result = _get_intent("contracts").get_by_id(params["id"])
        if not result.was_intent_successful:
            return _unwrap_intent_result(result)
        return _unwrap_intent_result(
            _get_intent("contracts").toggle_complete_status(result.data)
        )

    # -- Projects -----------------------------------------------------------
    if method == "projects.get_all":
        return _unwrap_intent_result(_get_intent("projects").get_all())
    if method == "projects.get_all_clients":
        clients_map = _get_intent("projects").get_all_clients_as_map()
        return {"ok": True, "data": _serialise(clients_map), "error": None}
    if method == "projects.get_all_contracts":
        contracts_map = _get_intent("projects").get_all_contracts_as_map()
        return {"ok": True, "data": _serialise(contracts_map), "error": None}
    if method == "projects.save":
        from tuttle.model import Project

        data = params["project"]
        clean = {
            k: v
            for k, v in data.items()
            if not k.startswith("_") and k not in ("contract", "timesheets", "invoices")
        }
        project = Project(**clean)
        return _unwrap_intent_result(_get_intent("projects").save_project(project))
    if method == "projects.delete":
        return _unwrap_intent_result(_get_intent("projects").delete(params["id"]))
    if method == "projects.toggle_completed":
        result = _get_intent("projects").get_by_id(params["id"])
        if not result.was_intent_successful:
            return _unwrap_intent_result(result)
        return _unwrap_intent_result(
            _get_intent("projects").toggle_project_completed_status(result.data)
        )

    # -- Invoicing ----------------------------------------------------------
    if method == "invoicing.get_all":
        from tuttle.app.core.formatting import fmt_currency

        ds = _get_intent("invoicing_ds")
        result = ds.get_all_invoices()
        if result.was_intent_successful and result.data:
            enriched = []
            for inv in result.data:
                d = _serialise(inv)
                currency = "EUR"
                if inv.contract:
                    currency = inv.contract.currency or "EUR"
                    d["contract_title"] = inv.contract.title or ""
                else:
                    d["contract_title"] = ""
                d["currency"] = currency
                d["client_name"] = ""
                d["project_title"] = ""
                if inv.contract and inv.contract.client:
                    d["client_name"] = inv.contract.client.name or ""
                if inv.project:
                    d["project_title"] = inv.project.title or ""
                d["sum_value"] = float(inv.sum)
                d["sum_formatted"] = fmt_currency(inv.sum, currency)
                d["vat_total_value"] = float(inv.VAT_total)
                d["vat_total_formatted"] = fmt_currency(inv.VAT_total, currency)
                d["total_value"] = float(inv.total)
                d["total_formatted"] = fmt_currency(inv.total, currency)
                items_enriched = []
                for item in inv.items or []:
                    item_d = _serialise(item)
                    item_d["unit_price_formatted"] = fmt_currency(
                        item.unit_price, currency
                    )
                    item_d["subtotal_value"] = float(item.subtotal)
                    item_d["subtotal_formatted"] = fmt_currency(item.subtotal, currency)
                    items_enriched.append(item_d)
                d["items"] = items_enriched
                if inv.rendered and inv.file_name:
                    pdf = Path.home() / ".tuttle" / "Invoices" / inv.file_name
                    d["pdf_path"] = str(pdf) if pdf.exists() else None
                else:
                    d["pdf_path"] = None
                enriched.append(d)
            return {"ok": True, "data": enriched, "error": None}
        return _unwrap_intent_result(result)
    if method == "invoicing.delete":
        return _unwrap_intent_result(
            _get_intent("invoicing").delete_invoice_by_id(params["id"])
        )
    if method == "invoicing.create":
        intent = _get_intent("invoicing")
        proj_result = _get_intent("projects").get_by_id(params["project_id"])
        if not proj_result.was_intent_successful:
            return _unwrap_intent_result(proj_result)
        project = proj_result.data
        invoice_date = datetime.date.fromisoformat(params["invoice_date"])
        from_date = datetime.date.fromisoformat(params["from_date"])
        to_date = datetime.date.fromisoformat(params["to_date"])
        manual_qty = params.get("manual_quantity")
        return _unwrap_intent_result(
            intent.create_invoice(
                invoice_date=invoice_date,
                project=project,
                from_date=from_date,
                to_date=to_date,
                render=params.get("render", True),
                manual_quantity=manual_qty,
            )
        )
    if method == "invoicing.toggle_sent":
        ds = _get_intent("invoicing_ds")
        result = ds.get_all_invoices()
        if not result.was_intent_successful:
            return _unwrap_intent_result(result)
        invoice = next((i for i in result.data if i.id == params["id"]), None)
        if not invoice:
            return {"ok": False, "data": None, "error": "Invoice not found"}
        return _unwrap_intent_result(
            _get_intent("invoicing").toggle_invoice_sent_status(invoice)
        )
    if method == "invoicing.toggle_paid":
        ds = _get_intent("invoicing_ds")
        result = ds.get_all_invoices()
        if not result.was_intent_successful:
            return _unwrap_intent_result(result)
        invoice = next((i for i in result.data if i.id == params["id"]), None)
        if not invoice:
            return {"ok": False, "data": None, "error": "Invoice not found"}
        return _unwrap_intent_result(
            _get_intent("invoicing").toggle_invoice_paid_status(invoice)
        )
    if method == "invoicing.toggle_cancelled":
        ds = _get_intent("invoicing_ds")
        result = ds.get_all_invoices()
        if not result.was_intent_successful:
            return _unwrap_intent_result(result)
        invoice = next((i for i in result.data if i.id == params["id"]), None)
        if not invoice:
            return {"ok": False, "data": None, "error": "Invoice not found"}
        return _unwrap_intent_result(
            _get_intent("invoicing").toggle_invoice_cancelled_status(invoice)
        )

    # -- Dashboard ----------------------------------------------------------
    if method == "dashboard.get_kpis":
        result = _get_intent("dashboard").get_kpis()
        if result.was_intent_successful and result.data is not None:
            from tuttle.app.core.formatting import fmt_currency

            kpi = result.data
            d = _serialise(kpi)
            tc = d.get("tax_currency", "EUR")
            d["total_revenue_ytd_formatted"] = fmt_currency(kpi.total_revenue_ytd, tc)
            d["outstanding_amount_formatted"] = fmt_currency(kpi.outstanding_amount, tc)
            d["overdue_amount_formatted"] = fmt_currency(kpi.overdue_amount, tc)
            d["vat_reserve_formatted"] = fmt_currency(kpi.vat_reserve, tc)
            d["income_tax_reserve_formatted"] = fmt_currency(kpi.income_tax_reserve, tc)
            d["spendable_income_formatted"] = fmt_currency(kpi.spendable_income, tc)
            if kpi.effective_hourly_rate is not None:
                d["effective_hourly_rate_formatted"] = fmt_currency(
                    kpi.effective_hourly_rate, tc
                )
            else:
                d["effective_hourly_rate_formatted"] = "—"
            if kpi.utilization_rate is not None:
                d["utilization_rate_formatted"] = f"{kpi.utilization_rate * 100:.0f}%"
            else:
                d["utilization_rate_formatted"] = "—"
            return {"ok": True, "data": d, "error": None}
        return _unwrap_intent_result(result)
    if method == "dashboard.get_monthly_chart_data":
        n = params.get("n_months", 12)
        return _unwrap_intent_result(
            _get_intent("dashboard").get_monthly_chart_data(n_months=n)
        )
    if method == "dashboard.get_project_budgets":
        return _unwrap_intent_result(_get_intent("dashboard").get_project_budgets())
    if method == "dashboard.get_financial_goals":
        return _unwrap_intent_result(_get_intent("dashboard").get_financial_goals())

    # -- Timeline -----------------------------------------------------------
    if method == "timeline.get_events":
        cat = params.get("category_filter")
        return _unwrap_intent_result(
            _get_intent("timeline").get_timeline_events(category_filter=cat)
        )

    # -- Demo ---------------------------------------------------------------
    if method == "demo.install":
        from tuttle.demo import install_demo_data
        from tuttle.migrations.run import run_migrations

        db_path = Path.home() / ".tuttle" / "tuttle.db"
        if db_path.exists():
            db_path.unlink()
        run_migrations(f"sqlite:///{db_path}")
        n = params.get("n_projects", 4)
        install_demo_data(
            n_projects=n,
            db_path=str(db_path),
            on_cache_timetracking_dataframe=lambda _: None,
        )
        _reset_intents()
        return {"ok": True, "data": None, "error": None}

    # -- DB lifecycle -------------------------------------------------------
    if method == "db.ensure":
        _ensure_db()
        return {"ok": True, "data": None, "error": None}

    if method == "db.exists":
        db_path = Path.home() / ".tuttle" / "tuttle.db"
        return {"ok": True, "data": db_path.exists(), "error": None}

    raise ValueError(f"Unknown method: {method}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main():
    """Read JSON-RPC requests from stdin, write responses to stdout."""
    logger.info("Tuttle RPC server starting…")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        response: Dict[str, Any]
        try:
            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method", "")
            params = request.get("params", {})

            result = _dispatch(method, params)
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:
            logger.exception(f"RPC error: {exc}")
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in dir() else None,
                "error": {
                    "code": -32603,
                    "message": str(exc),
                    "data": traceback.format_exc(),
                },
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
