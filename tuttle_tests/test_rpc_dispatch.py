"""Integration tests for the RPC dispatch round-trip.

Exercises the real code path the Electron shell uses:

    method string -> dispatch() -> intent -> DB -> to_rpc_dict()/dump() -> JSON

Catches detached-instance errors, missing modules, serialisation bugs, and
data-shape mismatches between the Python core and the frontend.
"""

import json
from pathlib import Path

import pytest

import tuttle.app.core.abstractions as abstractions
import tuttle.app_db as app_db_mod
from tuttle.app.core.dispatch import dispatch, _intents
from tuttle.app.core.rpc_utils import reset_all


# ---------------------------------------------------------------------------
# Fixture: isolated temp database with demo data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rpc_env(tmp_path_factory):
    """Set up an isolated ~/.tuttle with full demo data, return the temp dir."""
    tmp = tmp_path_factory.mktemp("tuttle_rpc")

    orig_app_init = app_db_mod.AppDatabase.__init__

    def _patched_init(self, app_dir=None):
        orig_app_init(self, app_dir=tmp)

    app_db_mod.AppDatabase.__init__ = _patched_init
    abstractions._active_db_path = tmp / "tuttle.db"

    try:
        result = dispatch("db.ensure", {})
        assert result["ok"], f"db.ensure failed: {result}"
        demo_result = dispatch("users.ensure_demo", {})
        assert demo_result["ok"], f"users.ensure_demo failed: {demo_result}"
        yield tmp
    finally:
        app_db_mod.AppDatabase.__init__ = orig_app_init
        abstractions._active_db_path = Path.home() / ".tuttle" / "tuttle.db"
        reset_all()
        _intents.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_ok(result: dict) -> dict:
    """Assert the envelope is a successful {ok, data, error} dict."""
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "ok" in result and "data" in result and "error" in result
    assert result["ok"] is True, f"RPC failed: {result.get('error')}"
    assert result["error"] is None
    json.dumps(result)
    return result


# ---------------------------------------------------------------------------
# 1. Boot lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """The startup sequence the Electron shell runs on every launch."""

    def test_db_ensure(self, rpc_env):
        result = dispatch("db.ensure", {})
        assert_ok(result)

    def test_users_list(self, rpc_env):
        result = dispatch("users.list", {})
        data = assert_ok(result)["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        demo = next((u for u in data if u.get("is_demo")), None)
        assert demo is not None, "Demo user missing from users.list"
        assert demo["db_file"] == "harry-tuttle.db"

    def test_users_get_active(self, rpc_env):
        result = dispatch("users.get_active", {})
        data = assert_ok(result)["data"]
        assert data is not None, "get_active returned None"
        assert "name" in data
        assert "db_file" in data
        assert "is_demo" in data
        assert "profile" in data

    def test_users_get_active_profile_shape(self, rpc_env):
        data = dispatch("users.get_active", {})["data"]
        profile = data["profile"]
        assert profile is not None, "Demo user should have a profile"
        assert "name" in profile
        assert "email" in profile
        assert "address" in profile
        assert isinstance(profile["address"], dict)


# ---------------------------------------------------------------------------
# 2. Read-only route resolution — every frontend RPC method that fetches data
# ---------------------------------------------------------------------------

READ_ROUTES = [
    "db.ensure",
    "users.list",
    "users.get_active",
    "projects.get_all",
    "projects.get_all_contracts",
    "contracts.get_all",
    "contracts.get_all_clients",
    "clients.get_all",
    "clients.get_all_contacts",
    "contacts.get_all",
    "invoicing.get_all",
    "invoicing.available_templates",
    "invoicing.available_languages",
    "preferences.get",
    "llm.get_config",
    "timetracking.get_summary",
    "timeline.get_events",
]


@pytest.mark.parametrize("method", READ_ROUTES)
def test_read_route_resolves(rpc_env, method):
    """Every read route returns a valid {ok, data, error} envelope."""
    result = dispatch(method, {})
    assert_ok(result)


DASHBOARD_ROUTES = [
    ("dashboard.get_kpis", {}),
    ("dashboard.get_monthly_chart_data", {"n_months": 12}),
]


@pytest.mark.parametrize("method,params", DASHBOARD_ROUTES)
def test_dashboard_routes(rpc_env, method, params):
    result = dispatch(method, params)
    assert_ok(result)


# ---------------------------------------------------------------------------
# 3. Serialization: relationship data must be present (not just FK ids)
# ---------------------------------------------------------------------------


class TestSerialization:
    """Entities with __rpc_relationships__ must include expanded relationships."""

    def test_projects_include_contract(self, rpc_env):
        data = dispatch("projects.get_all", {})["data"]
        assert isinstance(data, list) and len(data) > 0
        project = data[0]
        assert "contract" in project, "Project missing 'contract' relationship"
        assert isinstance(project["contract"], dict)
        assert "id" in project["contract"]

    def test_contracts_include_client(self, rpc_env):
        data = dispatch("contracts.get_all", {})["data"]
        assert isinstance(data, list) and len(data) > 0
        contract = data[0]
        assert "client" in contract, "Contract missing 'client' relationship"
        assert isinstance(contract["client"], dict)

    def test_contracts_include_projects(self, rpc_env):
        data = dispatch("contracts.get_all", {})["data"]
        contract = data[0]
        assert "projects" in contract, "Contract missing 'projects' relationship"
        assert isinstance(contract["projects"], list)

    def test_contracts_include_invoices(self, rpc_env):
        data = dispatch("contracts.get_all", {})["data"]
        contract = data[0]
        assert "invoices" in contract, "Contract missing 'invoices' relationship"
        assert isinstance(contract["invoices"], list)

    def test_clients_serialization(self, rpc_env):
        data = dispatch("clients.get_all", {})["data"]
        assert isinstance(data, list) and len(data) > 0
        has_contact = any(isinstance(c.get("invoicing_contact"), dict) for c in data)
        has_address = any(isinstance(c.get("address"), dict) for c in data)
        assert has_contact or has_address, "No client has a contact or address"

    def test_contacts_include_address(self, rpc_env):
        data = dispatch("contacts.get_all", {})["data"]
        assert isinstance(data, list) and len(data) > 0
        contact = data[0]
        assert "address" in contact, "Contact missing 'address' relationship"
        assert isinstance(contact["address"], dict)

    def test_invoices_include_items(self, rpc_env):
        data = dispatch("invoicing.get_all", {})["data"]
        assert isinstance(data, list) and len(data) > 0
        invoice = data[0]
        assert "items" in invoice, "Invoice missing 'items' relationship"
        assert isinstance(invoice["items"], list)

    def test_invoices_include_contract(self, rpc_env):
        data = dispatch("invoicing.get_all", {})["data"]
        invoice = data[0]
        assert "contract" in invoice, "Invoice missing 'contract' relationship"
        assert isinstance(invoice["contract"], dict)

    def test_invoices_computed_properties(self, rpc_env):
        data = dispatch("invoicing.get_all", {})["data"]
        invoice = data[0]
        for prop in ("sum", "total", "status", "due_date"):
            assert prop in invoice, f"Invoice missing computed property '{prop}'"

    def test_full_response_is_json_serializable(self, rpc_env):
        for method in [
            "projects.get_all",
            "contracts.get_all",
            "clients.get_all",
            "contacts.get_all",
            "invoicing.get_all",
        ]:
            result = dispatch(method, {})
            try:
                json.dumps(result)
            except (TypeError, ValueError) as exc:
                pytest.fail(f"{method} response not JSON-serializable: {exc}")
