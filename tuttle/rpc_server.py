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
# Entity serialisation helpers (include nested relations)
# ---------------------------------------------------------------------------


def _client_to_rpc_dict(client) -> Dict[str, Any]:
    """Serialise a Client with nested invoicing_contact and address."""
    d = _serialise(client)
    ic = client.invoicing_contact
    if ic:
        icd = _serialise(ic)
        if ic.address:
            icd["address"] = _serialise(ic.address)
        d["invoicing_contact"] = icd
    return d


def _contract_to_rpc_dict(contract, include_relations: bool = True) -> Dict[str, Any]:
    """Serialise a Contract with nested client and relationship counts."""
    d = _serialise(contract)
    if contract.client:
        d["client"] = _serialise(contract.client)
    if include_relations:
        d["projects"] = [
            {"id": p.id, "title": p.title} for p in (contract.projects or [])
        ]
        d["invoices"] = [{"id": inv.id} for inv in (contract.invoices or [])]
    return d


def _project_to_rpc_dict(project) -> Dict[str, Any]:
    """Serialise a Project with nested contract (and its client), no circular refs."""
    d = _serialise(project)
    if project.contract:
        d["contract"] = _contract_to_rpc_dict(project.contract, include_relations=False)
    return d


def _patch_scalars_from_rpc(instance: Any, updates: Dict[str, Any], skip: set) -> None:
    """Apply JSON payload fields onto a persisted SQLModel row (in-place).

    Handles date coercion for *_date fields and empty-string-to-None for optional dates.
    """
    for k, v in updates.items():
        if k in skip or k.startswith("_"):
            continue
        if v == "" and k.endswith("_date"):
            v = None
        if isinstance(v, str) and k.endswith("_date") and v and len(v) >= 10:
            try:
                v = datetime.date.fromisoformat(v[:10])
            except ValueError:
                pass
        setattr(instance, k, v)


# ---------------------------------------------------------------------------
# Method dispatch table
# ---------------------------------------------------------------------------


def _get_app_db():
    from tuttle.app_db import AppDatabase

    return AppDatabase()


def _ensure_user_db(db_path: Path):
    """Ensure a per-user database exists and migrations are applied."""
    from tuttle.migrations.run import run_migrations

    run_migrations(f"sqlite:///{db_path}")


def _switch_to_user_db(db_file: str):
    """Switch the active per-user database and reset all intent singletons."""
    from tuttle.app.core.abstractions import set_active_db

    app_db = _get_app_db()
    db_path = app_db.get_user_db_path(db_file)
    _ensure_user_db(db_path)
    set_active_db(db_path)
    app_db.set_active(db_file)
    _reset_intents()
    logger.info(f"Switched to user DB: {db_file}")


def _ensure_demo_user():
    """Ensure the Harry Tuttle demo user is registered (does not install data)."""
    from tuttle.demo import install_demo_data
    from tuttle.migrations.run import run_migrations

    app_db = _get_app_db()
    if app_db.get_user_by_db_file("harry-tuttle.db"):
        return
    reg = app_db.add_user(
        name="Harry Tuttle",
        subtitle="Heating Engineer",
        is_demo=True,
        db_file="harry-tuttle.db",
    )
    db_path = app_db.get_user_db_path(reg.db_file)
    if db_path.exists():
        db_path.unlink()
    run_migrations(f"sqlite:///{db_path}")
    install_demo_data(
        n_projects=4,
        db_path=str(db_path),
        on_cache_timetracking_dataframe=lambda _: None,
    )
    logger.info("Demo user Harry Tuttle created with heating-repair data")


def _ensure_db():
    """Ensure app.db + demo user + last-active user DB exist and are migrated."""
    app_db = _get_app_db()
    app_db.ensure()
    app_db.migrate_llm_config_from_json()
    _ensure_demo_user()

    last = app_db.get_last_active()
    if last:
        _switch_to_user_db(last.db_file)
    else:
        users = app_db.list_users()
        if users:
            _switch_to_user_db(users[0].db_file)


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
        result = _get_intent("clients").get_all()
        if result.was_intent_successful and result.data:
            enriched = [_client_to_rpc_dict(c) for c in result.data]
            return {"ok": True, "data": enriched, "error": None}
        return _unwrap_intent_result(result)
    if method == "clients.get_by_id":
        result = _get_intent("clients").get_by_id(params["id"])
        if result.was_intent_successful and result.data:
            return {"ok": True, "data": _client_to_rpc_dict(result.data), "error": None}
        return _unwrap_intent_result(result)
    if method == "clients.get_all_contacts":
        contacts_map = _get_intent("clients").get_all_contacts_as_map()
        return {"ok": True, "data": _serialise(contacts_map), "error": None}
    if method == "clients.save":
        from tuttle.model import Client, Contact, Address

        raw = params["client"]
        data = dict(raw)
        contact_data = dict(data.pop("invoicing_contact", {}) or {})
        addr_data = dict(contact_data.pop("address", {}) or {})
        client_id = data.get("id")
        intent = _get_intent("clients")
        contacts_intent = _get_intent("contacts")

        if client_id:
            existing = intent.get_by_id(client_id)
            if not existing.was_intent_successful or not existing.data:
                return {"ok": False, "data": None, "error": "Client not found"}
            client = existing.data
            for k, v in data.items():
                if not k.startswith("_") and k not in (
                    "id",
                    "contracts",
                    "invoicing_contact_id",
                    "invoicing_contact",
                ):
                    setattr(client, k, v)

            contact_id = contact_data.get("id")
            if contact_id:
                cres = contacts_intent.get_by_id(contact_id)
                if not cres.was_intent_successful or not cres.data:
                    return {
                        "ok": False,
                        "data": None,
                        "error": "Invoicing contact not found",
                    }
                contact = cres.data
                for k, v in contact_data.items():
                    if not k.startswith("_") and k not in (
                        "id",
                        "invoicing_contact_of",
                        "address",
                        "address_id",
                    ):
                        setattr(contact, k, v)
                if contact.address:
                    for k, v in addr_data.items():
                        if not k.startswith("_") and k != "id":
                            setattr(contact.address, k, v)
                elif addr_data:
                    contact.address = Address(
                        **{
                            k: v
                            for k, v in addr_data.items()
                            if k != "id" and not k.startswith("_")
                        }
                    )
                client.invoicing_contact = contact
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
                        for k, v in contact_data.items()
                        if not k.startswith("_")
                        and k not in ("invoicing_contact_of", "address_id")
                    },
                )
                client.invoicing_contact = contact
            return _unwrap_intent_result(intent.save_client(client))

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
        return _unwrap_intent_result(intent.save_client(client))
    if method == "clients.delete":
        return _unwrap_intent_result(_get_intent("clients").delete(params["id"]))

    # -- Contracts ----------------------------------------------------------
    if method == "contracts.get_all":
        result = _get_intent("contracts").get_all()
        if result.was_intent_successful and result.data:
            enriched = [_contract_to_rpc_dict(c) for c in result.data]
            return {"ok": True, "data": enriched, "error": None}
        return _unwrap_intent_result(result)
    if method == "contracts.get_by_id":
        result = _get_intent("contracts").get_by_id(params["id"])
        if result.was_intent_successful and result.data:
            return {
                "ok": True,
                "data": _contract_to_rpc_dict(result.data),
                "error": None,
            }
        return _unwrap_intent_result(result)
    if method == "contracts.get_all_clients":
        clients_map = _get_intent("contracts").get_all_clients_as_map()
        return {"ok": True, "data": _serialise(clients_map), "error": None}
    if method == "contracts.get_default_currency":
        return _unwrap_intent_result(_get_intent("contracts").get_default_currency())
    if method == "contracts.save":
        from tuttle.model import Contract

        data = params["contract"]
        clean = {
            k: v
            for k, v in data.items()
            if not k.startswith("_") and k not in ("client", "projects", "invoices")
        }
        contract_id = clean.get("id")
        intent = _get_intent("contracts")
        skip_patch = {"id", "client", "projects", "invoices"}

        if contract_id:
            res = intent.get_by_id(contract_id)
            if not res.was_intent_successful or not res.data:
                return {"ok": False, "data": None, "error": "Contract not found"}
            contract = res.data
            _patch_scalars_from_rpc(contract, clean, skip_patch)
            return _unwrap_intent_result(intent.save_contract(contract))

        new_data = {k: v for k, v in clean.items() if k != "id"}
        for k in list(new_data.keys()):
            if k.endswith("_date") and isinstance(new_data[k], str) and new_data[k]:
                try:
                    new_data[k] = datetime.date.fromisoformat(new_data[k][:10])
                except ValueError:
                    pass
            elif k.endswith("_date") and new_data[k] == "":
                new_data[k] = None
        return _unwrap_intent_result(intent.save_contract(Contract(**new_data)))
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
        result = _get_intent("projects").get_all()
        if result.was_intent_successful and result.data:
            enriched = [_project_to_rpc_dict(p) for p in result.data]
            return {"ok": True, "data": enriched, "error": None}
        return _unwrap_intent_result(result)
    if method == "projects.get_by_id":
        result = _get_intent("projects").get_by_id(params["id"])
        if result.was_intent_successful and result.data:
            return {
                "ok": True,
                "data": _project_to_rpc_dict(result.data),
                "error": None,
            }
        return _unwrap_intent_result(result)
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
        project_id = clean.get("id")
        intent = _get_intent("projects")
        skip_patch = {"id", "contract", "timesheets", "invoices"}

        if project_id:
            res = intent.get_by_id(project_id)
            if not res.was_intent_successful or not res.data:
                return {"ok": False, "data": None, "error": "Project not found"}
            project = res.data
            _patch_scalars_from_rpc(project, clean, skip_patch)
            return _unwrap_intent_result(intent.save_project(project))

        new_data = {k: v for k, v in clean.items() if k != "id"}
        for k in list(new_data.keys()):
            if k.endswith("_date") and isinstance(new_data[k], str) and new_data[k]:
                try:
                    new_data[k] = datetime.date.fromisoformat(new_data[k][:10])
                except ValueError:
                    pass
            elif k.endswith("_date") and new_data[k] == "":
                new_data[k] = None
        return _unwrap_intent_result(intent.save_project(Project(**new_data)))
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

    # -- LLM ---------------------------------------------------------------
    if method == "llm.get_config":
        from tuttle.llm import load_config

        config = load_config()
        return {"ok": True, "data": config.model_dump(), "error": None}

    if method == "llm.save_config":
        from tuttle.llm import LLMConfig, save_config

        config = LLMConfig(**params.get("config", {}))
        saved = save_config(config)
        return {"ok": True, "data": saved.model_dump(), "error": None}

    if method == "llm.get_models":
        from tuttle.llm import get_available_models

        base_url = params.get("base_url", "http://localhost:11434")
        models = get_available_models(base_url)
        return {"ok": True, "data": models, "error": None}

    if method == "llm.parse_document":
        from tuttle.llm import parse_document, load_config as _load_llm

        file_base64 = params["file_base64"]
        file_name = params["file_name"]
        entity_type = params.get("entity_type", "contact")
        config = _load_llm()
        items = parse_document(file_base64, file_name, entity_type, config)
        return {"ok": True, "data": items, "error": None}

    # -- Users --------------------------------------------------------------
    if method == "users.list":
        app_db = _get_app_db()
        users = app_db.list_users()
        return {
            "ok": True,
            "data": [_serialise(u) for u in users],
            "error": None,
        }

    if method == "users.create":
        from tuttle.model import User, Address, BankAccount
        from tuttle.migrations.run import run_migrations
        from sqlmodel import Session as SqlSession, create_engine as sql_create_engine

        app_db = _get_app_db()
        name = params["name"]
        subtitle = params.get("subtitle", "")
        reg = app_db.add_user(name=name, subtitle=subtitle)
        db_path = app_db.get_user_db_path(reg.db_file)
        run_migrations(f"sqlite:///{db_path}")
        engine = sql_create_engine(f"sqlite:///{db_path}")
        with SqlSession(engine) as s:
            address = Address(
                street=params.get("street", ""),
                number=params.get("street_num", ""),
                postal_code=params.get("postal_code", ""),
                city=params.get("city", ""),
                country=params.get("country", ""),
            )
            user = User(
                name=name,
                subtitle=subtitle,
                email=params.get("email", ""),
                phone_number=params.get("phone", ""),
                website=params.get("website", ""),
                operating_country=params.get("operating_country", "Germany"),
                VAT_number=params.get("vat_number", ""),
                address=address,
            )
            s.add(user)
            s.commit()
        engine.dispose()
        _switch_to_user_db(reg.db_file)
        return {"ok": True, "data": _serialise(reg), "error": None}

    if method == "users.switch":
        db_file = params["db_file"]
        _switch_to_user_db(db_file)
        return {"ok": True, "data": None, "error": None}

    if method == "users.delete":
        db_file = params["db_file"]
        app_db = _get_app_db()
        removed = app_db.remove_user(db_file)
        if removed:
            _reset_intents()
        return {"ok": True, "data": removed, "error": None}

    if method == "users.get_active":
        from tuttle.app.core.abstractions import get_active_db

        app_db = _get_app_db()
        active_path = get_active_db()
        active_file = active_path.name
        reg = app_db.get_user_by_db_file(active_file)
        if not reg:
            return {"ok": True, "data": None, "error": None}
        from tuttle.app.auth.data_source import UserDataSource

        try:
            ds = UserDataSource()
            profile = ds.get_user()
            data = _serialise(reg)
            if profile:
                data["profile"] = _serialise(profile)
                if profile.address:
                    data["profile"]["address"] = _serialise(profile.address)
            return {"ok": True, "data": data, "error": None}
        except Exception:
            return {"ok": True, "data": _serialise(reg), "error": None}

    if method == "users.ensure_demo":
        _ensure_demo_user()
        app_db = _get_app_db()
        reg = app_db.get_user_by_db_file("harry-tuttle.db")
        return {"ok": True, "data": _serialise(reg) if reg else None, "error": None}

    # -- Settings -----------------------------------------------------------
    if method == "settings.get":
        app_db = _get_app_db()
        val = app_db.get_setting(params["key"])
        return {"ok": True, "data": val, "error": None}

    if method == "settings.set":
        app_db = _get_app_db()
        app_db.set_setting(params["key"], params["value"])
        return {"ok": True, "data": None, "error": None}

    if method == "settings.get_all":
        app_db = _get_app_db()
        prefix = params.get("prefix")
        data = app_db.get_all_settings(prefix=prefix)
        return {"ok": True, "data": data, "error": None}

    # -- Demo (legacy, now wraps users.ensure_demo) -------------------------
    if method == "demo.install":
        result = _dispatch("users.ensure_demo", {})
        if result.get("ok") and result.get("data"):
            db_file = result["data"].get("db_file", "harry-tuttle.db")
            _switch_to_user_db(db_file)
        return result

    # -- DB lifecycle -------------------------------------------------------
    if method == "db.ensure":
        _ensure_db()
        return {"ok": True, "data": None, "error": None}

    if method == "db.exists":
        from tuttle.app.core.abstractions import get_active_db

        return {"ok": True, "data": get_active_db().exists(), "error": None}

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
