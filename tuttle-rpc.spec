# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the tuttle RPC sidecar.

Bundles tuttle/rpc_server.py as the entry point, pulling in the full
CPython interpreter, the entire tuttle package, all Python dependencies,
native shared libraries, and data files.  The output is a self-contained
directory (dist/tuttle-rpc/) that runs without a Python installation.

Usage:
    pyinstaller tuttle-rpc.spec
"""

import sys
from importlib.util import find_spec
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Data files that PyInstaller can't discover from imports alone
# ---------------------------------------------------------------------------

datas = [
    ("templates", "templates"),
    ("tuttle/migrations", "tuttle/migrations"),
    ("tuttle/tax_data", "tuttle/tax_data"),
]

# rfc3987_syntax ships non-Python data files that PyInstaller misses
_rfc_spec = find_spec("rfc3987_syntax")
if _rfc_spec and _rfc_spec.submodule_search_locations:
    datas.append((_rfc_spec.submodule_search_locations[0], "rfc3987_syntax"))

# ---------------------------------------------------------------------------
# Hidden imports -- lazily imported modules PyInstaller can't trace
# ---------------------------------------------------------------------------

hiddenimports = [
    # Intent classes (loaded on first RPC call)
    "tuttle.app.contacts.intent",
    "tuttle.app.clients.intent",
    "tuttle.app.contracts.intent",
    "tuttle.app.projects.intent",
    "tuttle.app.invoicing.intent",
    "tuttle.app.invoicing.data_source",
    "tuttle.app.dashboard.intent",
    "tuttle.app.timeline.intent",
    "tuttle.app.core.database_storage_impl",
    "tuttle.app.core.formatting",
    "tuttle.model",
    "tuttle.demo",
    "tuttle.migrations.run",
    # Alembic internals
    "alembic",
    "alembic.config",
    "alembic.command",
    "alembic.script",
    "alembic.runtime.environment",
    "alembic.runtime.migration",
    # Babel number/currency formatting
    "babel.numbers",
    # SQLModel / SQLAlchemy backends
    "sqlmodel",
    "sqlalchemy.dialects.sqlite",
    # WeasyPrint rendering chain
    "weasyprint",
    "cairocffi",
    "cssselect2",
    "tinycss2",
    "pyphen",
    # Other potentially dynamic imports
    "pycountry",
    "pycountry.databases",
    "faker",
    "faker.providers",
    "ics",
    "loguru",
    "pandera",
    "PyPDF2",
    "fitz",  # pymupdf
]

# ---------------------------------------------------------------------------
# Excludes -- large packages the RPC server never imports
# ---------------------------------------------------------------------------

excludes = [
    "tkinter",
    "_tkinter",
]

# ---------------------------------------------------------------------------
# Analysis & build
# ---------------------------------------------------------------------------

a = Analysis(
    ["tuttle/rpc_server.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tuttle-rpc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # RPC server communicates via stdio
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="tuttle-rpc",
)
