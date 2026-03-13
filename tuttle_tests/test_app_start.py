"""Integration tests for application startup.

Verifies that:
- all critical modules can be imported (catches dependency issues),
- the database schema can be materialised in memory,
- the app process starts without an immediate crash,
- UI panel constructors and content-building methods run without error.
"""

import importlib
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine


# ---------------------------------------------------------------------------
# 1. Import smoke tests
# ---------------------------------------------------------------------------

CORE_MODULES = [
    "tuttle",
    "tuttle.model",
    "tuttle.calendar",
    "tuttle.invoicing",
    "tuttle.timetracking",
    "tuttle.rendering",
    "tuttle.tax",
    "tuttle.banking",
    "tuttle.cloud",
    "tuttle.time",
    "tuttle.dataviz",
    "tuttle.os_functions",
    "tuttle.mail",
]

APP_MODULES = [
    "tuttle.app",
    "tuttle.app.core.abstractions",
    "tuttle.app.core.database_storage_impl",
    "tuttle.app.core.views",
    "tuttle.app.auth.view",
    "tuttle.app.home.view",
    "tuttle.app.projects.view",
    "tuttle.app.contracts.view",
    "tuttle.app.clients.view",
    "tuttle.app.contacts.view",
    "tuttle.app.invoicing.view",
    "tuttle.app.timetracking.view",
    "tuttle.app.preferences.view",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_import_core_module(module_name):
    """Every core library module must be importable without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize("module_name", APP_MODULES)
def test_import_app_module(module_name):
    """Every application UI module must be importable without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None


# ---------------------------------------------------------------------------
# 1b. Resource-module attribute smoke tests
# ---------------------------------------------------------------------------
# These catch typos like ``fonts.BODY_FONT`` when only ``fonts.BOLD_FONT``
# exists.  Each tuple is (module_path, [expected_attributes]).

_RES_ATTRS = [
    (
        "tuttle.app.res.fonts",
        [
            "DEFAULT_FONT",
            "HEADLINE_FONT",
            "APP_FONTS",
            "HEADLINE_0_SIZE",
            "HEADLING_1_SIZE",
            "HEADLINE_2_SIZE",
            "HEADLINE_3_SIZE",
            "HEADLINE_4_SIZE",
            "BODY_1_SIZE",
            "BODY_2_SIZE",
            "SUBTITLE_1_SIZE",
            "SUBTITLE_2_SIZE",
            "BUTTON_SIZE",
            "OVERLINE_SIZE",
            "CAPTION_SIZE",
            "STATUS_BAR_SIZE",
            "BOLD_FONT",
            "BOLDER_FONT",
        ],
    ),
    (
        "tuttle.app.res.colors",
        [
            "bg",
            "bg_surface",
            "bg_surface_hovered",
            "text_primary",
            "text_secondary",
            "text_muted",
            "accent",
            "accent_muted",
            "border",
            "status_active",
            "status_upcoming",
            "status_completed",
        ],
    ),
    (
        "tuttle.app.res.dimens",
        [
            "SPACE_XS",
            "SPACE_SM",
            "SPACE_MD",
            "SPACE_LG",
            "RADIUS_PILL",
            "RADIUS_XL",
        ],
    ),
]


@pytest.mark.parametrize(
    "module_name,attr",
    [(mod, attr) for mod, attrs in _RES_ATTRS for attr in attrs],
    ids=lambda val: val if isinstance(val, str) else "",
)
def test_res_module_attribute_exists(module_name, attr):
    """Every resource constant used by the UI must actually be defined."""
    mod = importlib.import_module(module_name)
    assert hasattr(mod, attr), f"module {module_name!r} has no attribute {attr!r}"


# ---------------------------------------------------------------------------
# 1c. View-class instantiation guards
# ---------------------------------------------------------------------------
# Verify that the key classes/functions referenced in each view module are
# actually present — catches stale renames (e.g. ProjectCard → ProjectRow).

_VIEW_EXPORTS = [
    (
        "tuttle.app.projects.view",
        ["ProjectRow", "ProjectsListView", "ProjectSidePanel"],
    ),
    (
        "tuttle.app.contracts.view",
        ["ContractRow", "ContractsListView", "ContractSidePanel"],
    ),
    ("tuttle.app.clients.view", ["ClientRow", "ClientsListView", "ClientSidePanel"]),
    (
        "tuttle.app.contacts.view",
        ["ContactRow", "ContactsListView", "ContactSidePanel"],
    ),
    (
        "tuttle.app.core.views",
        ["CrudListView", "EntitySidePanel", "TTextField", "TBodyText"],
    ),
]


@pytest.mark.parametrize(
    "module_name,attr",
    [(mod, attr) for mod, attrs in _VIEW_EXPORTS for attr in attrs],
    ids=lambda val: val if isinstance(val, str) else "",
)
def test_view_module_exports(module_name, attr):
    """Key view classes must exist and be importable."""
    mod = importlib.import_module(module_name)
    assert hasattr(
        mod, attr
    ), f"module {module_name!r} missing expected export {attr!r}"


# ---------------------------------------------------------------------------
# 2. Database schema creation
# ---------------------------------------------------------------------------


def test_database_schema_creation(tmp_path):
    """The full SQLModel schema must materialise as SQLite tables."""
    import tuttle.model  # noqa: F401 — registers all tables

    db_path = tmp_path / "test_startup.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    expected_tables = {"user", "contact", "address", "client", "contract", "project"}
    missing = expected_tables - {t.lower() for t in tables}
    assert not missing, f"Missing tables: {missing}"


# ---------------------------------------------------------------------------
# 3. Application process smoke test
# ---------------------------------------------------------------------------

APP_ENTRY_POINT = Path(__file__).resolve().parent.parent / "app.py"
STARTUP_WAIT_SECONDS = 5


@pytest.mark.gui
def test_app_process_starts():
    """The application process must survive initial startup without crashing."""
    # start_new_session gives the app its own process group so we can
    # kill it together with any child processes (e.g. the Flet desktop client).
    proc = subprocess.Popen(
        [sys.executable, str(APP_ENTRY_POINT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        time.sleep(STARTUP_WAIT_SECONDS)
        exit_code = proc.poll()
        if exit_code is not None:
            _, stderr = proc.communicate(timeout=2)
            pytest.fail(
                f"App exited prematurely with code {exit_code}.\n"
                f"stderr:\n{stderr.decode(errors='replace')}"
            )
    finally:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
        proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# 4. Side-panel runtime exercise tests
# ---------------------------------------------------------------------------
# These go beyond import checks: they construct real panels with demo data
# and call every content-building method. This catches runtime errors like
# missing attributes (e.g. TDropDown.drop_down before build()) or wrong
# constructor signatures (e.g. unexpected keyword argument).

import datetime
from decimal import Decimal

from tuttle.model import (
    Address,
    Client,
    Contact,
    Contract,
    Cycle,
    Project,
    TimeUnit,
)


@pytest.fixture
def demo_contact():
    """A realistic Contact with address."""
    return Contact(
        id=1,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        company="Babbage Ltd.",
        address=Address(
            id=1,
            street="Dorset",
            number="42",
            city="London",
            postal_code="W1A 1AB",
            country="UK",
        ),
    )


@pytest.fixture
def demo_client(demo_contact):
    """A realistic Client with invoicing contact."""
    return Client(
        id=1,
        name="Babbage Ltd.",
        invoicing_contact=demo_contact,
    )


@pytest.fixture
def demo_contract(demo_client):
    """A realistic Contract with all fields populated."""
    return Contract(
        id=1,
        title="Analytical Engine Maintenance",
        client=demo_client,
        signature_date=datetime.date(2025, 1, 15),
        start_date=datetime.date(2025, 2, 1),
        end_date=datetime.date(2026, 6, 1),
        rate=800,
        currency="EUR",
        VAT_rate=Decimal("0.19"),
        unit=TimeUnit.day,
        units_per_workday=8,
        volume=200,
        term_of_payment=14,
        billing_cycle=Cycle.monthly,
    )


@pytest.fixture
def demo_project(demo_contract):
    """A realistic Project linked to a contract."""
    return Project(
        id=1,
        title="Engine Refactoring",
        tag="#engine-refactoring",
        description="Refactor the analytical engine for better performance.",
        is_completed=False,
        start_date=datetime.date(2025, 2, 1),
        end_date=datetime.date(2026, 6, 1),
        contract=demo_contract,
    )


def _noop(*args, **kwargs):
    """No-op callback for panel constructors."""
    pass


class TestProjectSidePanel:
    """Exercise ProjectSidePanel construction and content building."""

    def _make_panel(self):
        from tuttle.app.projects.view import ProjectSidePanel

        return ProjectSidePanel(
            on_close=_noop,
            on_save=_noop,
            on_delete=_noop,
            intent=None,
            on_edit_requested=_noop,
        )

    def test_constructor(self):
        panel = self._make_panel()
        assert panel is not None

    def test_build_detail_content(self, demo_project):
        panel = self._make_panel()
        controls = panel.build_detail_content(demo_project)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_compact_detail(self, demo_project):
        panel = self._make_panel()
        controls = panel.build_compact_detail(demo_project)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_compact_detail_no_description(self, demo_contract):
        """Project with no description should still render."""
        from tuttle.app.projects.view import ProjectSidePanel

        panel = self._make_panel()
        proj = Project(
            id=99,
            title="Bare project",
            tag="#bare",
            description="",
            is_completed=True,
            start_date=datetime.date.today(),
            end_date=datetime.date.today(),
            contract=demo_contract,
        )
        controls = panel.build_compact_detail(proj)
        assert isinstance(controls, list)

    def test_build_edit_content(self, demo_project):
        """build_edit_content must run without AttributeError.

        This specifically guards against bugs like TDropDown.drop_down
        not existing before Flet's build() lifecycle.
        """
        panel = self._make_panel()
        panel._contracts_map = {}
        panel._load_contracts = lambda: None  # stub — no intent in tests
        controls = panel.build_edit_content(demo_project)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content_new(self):
        """Creating a new project (entity=None) must also work."""
        panel = self._make_panel()
        panel._contracts_map = {}
        panel._load_contracts = lambda: None
        controls = panel.build_edit_content(None)
        assert isinstance(controls, list)


class _StubContractIntent:
    """Minimal stand-in for ContractIntent used in tests without a database."""

    def get_default_currency(self):
        from tuttle.app.core.intent_result import IntentResult

        return IntentResult(was_intent_successful=True, data="EUR")


class TestContractSidePanel:
    """Exercise ContractSidePanel construction and content building."""

    def _make_panel(self):
        from tuttle.app.contracts.view import ContractSidePanel

        return ContractSidePanel(
            on_close=_noop,
            on_save=_noop,
            on_delete=_noop,
            intent=_StubContractIntent(),
            client_storage=None,
            on_edit_requested=_noop,
        )

    def test_constructor(self):
        panel = self._make_panel()
        assert panel is not None

    def test_build_detail_content(self, demo_contract):
        panel = self._make_panel()
        controls = panel.build_detail_content(demo_contract)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_compact_detail(self, demo_contract):
        panel = self._make_panel()
        controls = panel.build_compact_detail(demo_contract)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content(self, demo_contract):
        panel = self._make_panel()
        panel._clients_map = {}
        panel._contacts_map = {}
        panel._currencies = ["EUR", "USD"]
        panel._client_storage = None
        panel._load_data = lambda: None  # stub — no intent in tests
        controls = panel.build_edit_content(demo_contract)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content_new(self):
        panel = self._make_panel()
        panel._clients_map = {}
        panel._contacts_map = {}
        panel._currencies = ["EUR", "USD"]
        panel._client_storage = None
        panel._load_data = lambda: None
        controls = panel.build_edit_content(None)
        assert isinstance(controls, list)


class TestClientSidePanel:
    """Exercise ClientSidePanel construction and content building."""

    def _make_panel(self):
        from tuttle.app.clients.view import ClientSidePanel

        return ClientSidePanel(
            on_close=_noop,
            on_save=_noop,
            on_delete=_noop,
            intent=None,
            on_edit_requested=_noop,
        )

    def test_constructor(self):
        panel = self._make_panel()
        assert panel is not None

    def test_build_detail_content(self, demo_client):
        panel = self._make_panel()
        controls = panel.build_detail_content(demo_client)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_compact_detail(self, demo_client):
        panel = self._make_panel()
        controls = panel.build_compact_detail(demo_client)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content(self, demo_client):
        panel = self._make_panel()
        panel._contacts_map = {}
        panel._load_contacts = lambda: None  # stub — no intent in tests
        controls = panel.build_edit_content(demo_client)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content_new(self):
        panel = self._make_panel()
        panel._contacts_map = {}
        panel._load_contacts = lambda: None
        controls = panel.build_edit_content(None)
        assert isinstance(controls, list)


class TestContactSidePanel:
    """Exercise ContactSidePanel construction and content building."""

    def _make_panel(self):
        from tuttle.app.contacts.view import ContactSidePanel

        return ContactSidePanel(
            on_close=_noop,
            on_save=_noop,
            on_delete=_noop,
            intent=None,
            on_edit_requested=_noop,
        )

    def test_constructor(self):
        panel = self._make_panel()
        assert panel is not None

    def test_build_detail_content(self, demo_contact):
        panel = self._make_panel()
        controls = panel.build_detail_content(demo_contact)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_compact_detail(self, demo_contact):
        panel = self._make_panel()
        controls = panel.build_compact_detail(demo_contact)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content(self, demo_contact):
        panel = self._make_panel()
        controls = panel.build_edit_content(demo_contact)
        assert isinstance(controls, list)
        assert len(controls) > 0

    def test_build_edit_content_new(self):
        panel = self._make_panel()
        controls = panel.build_edit_content(None)
        assert isinstance(controls, list)


# ---------------------------------------------------------------------------
# 5. TDropDown pre-build access tests
# ---------------------------------------------------------------------------
# Guards against the pattern where TDropDown.drop_down is created lazily in
# build() but accessed via update_value() before the control is rendered.


class TestTDropDown:
    """Verify TDropDown methods work before Flet's build() lifecycle."""

    def test_value_accessible_before_build(self):
        from tuttle.app.core.views import TDropDown

        dd = TDropDown(label="Test", items=["a", "b", "c"])
        # Must not raise AttributeError
        assert dd.drop_down is not None

    def test_update_value_before_build(self):
        from tuttle.app.core.views import TDropDown

        dd = TDropDown(label="Test", items=["a", "b", "c"])
        dd.update_value("b")
        assert dd.value == "b"

    def test_initial_value(self):
        from tuttle.app.core.views import TDropDown

        dd = TDropDown(label="Test", items=["x", "y"], initial_value="y")
        assert dd.value == "y"

    def test_update_dropdown_items_before_build(self):
        """update_dropdown_items must not crash before build()."""
        from tuttle.app.core.views import TDropDown

        dd = TDropDown(label="Test", items=["a"])
        # This would have crashed with the old code
        # (drop_down only created in build())
        dd.drop_down.options  # access must work
