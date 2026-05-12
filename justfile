# Tuttle – development & build tasks

set dotenv-load := false

repo     := justfile_directory()
electron := repo / "tuttle-electron"
venv     := repo / ".venv"
python   := venv / "bin/python"
app      := electron / "release/mac-arm64/Tuttle.app"

# ── Development ─────────────────────────────────────────────────────────────

# Vite dev server with hot reload (no packaged .app, no calendar access)
dev:
    cd {{electron}} && npx vite

# ── Build ───────────────────────────────────────────────────────────────────

# Build the Python RPC sidecar with PyInstaller
build-sidecar:
    {{python}} -m PyInstaller --clean --noconfirm {{repo}}/tuttle-rpc.spec

# Build the Electron renderer (Vite + TypeScript)
build-renderer:
    cd {{electron}} && npm run build

# Remove previous packaged app to avoid launching stale builds
clean-app:
    rm -rf "{{electron}}/release"

# Package the Electron .app (requires build-sidecar + build-renderer first)
pack target="dir":
    cd {{electron}} && CSC_IDENTITY_AUTO_DISCOVERY=false npx electron-builder --mac {{target}}
    @echo "Ad-hoc signing all binaries…"
    find "{{app}}" -type f \( -name '*.dylib' -o -name '*.so' -o -perm +111 \) -exec codesign --force --sign - {} \; 2>/dev/null || true
    codesign --force --deep --sign - "{{app}}"

# Full build: sidecar → renderer → package (pass "dmg" for .dmg)
build target="dir": clean-app build-sidecar build-renderer (pack target)
    @echo "✓ {{electron}}/release/"

# Create a beta .zip with an install script that strips quarantine
beta: (build "dir")
    #!/usr/bin/env bash
    set -euo pipefail
    staging="{{electron}}/release/beta"
    rm -rf "$staging"
    mkdir -p "$staging"
    cp -R "{{app}}" "$staging/"
    cat > "$staging/Install Tuttle.command" << 'SCRIPT'
    #!/bin/bash
    set -e
    cd "$(dirname "$0")"
    dest="/Applications/Tuttle.app"
    [ -d "$dest" ] && rm -rf "$dest"
    cp -R "Tuttle.app" "$dest"
    xattr -cr "$dest"
    echo ""
    echo "✓ Tuttle installed to /Applications"
    echo "  You can now open it from Launchpad or Spotlight."
    echo ""
    read -n1 -rsp "Press any key to close…"
    SCRIPT
    chmod +x "$staging/Install Tuttle.command"
    cd "{{electron}}/release"
    zip -ry "Tuttle-beta.zip" beta/
    rm -rf "$staging"
    echo "✓ {{electron}}/release/Tuttle-beta.zip"

# ── Run ─────────────────────────────────────────────────────────────────────

# Launch the packaged Tuttle.app
run:
    @test -d "{{app}}" || (echo "No app found. Run 'just build' first." && exit 1)
    open "{{app}}"

# Build and run
br: build run

# ── Calendar helper (dev-mode workaround) ───────────────────────────────────

# Build the TuttleCalendar.app helper and request calendar access
calendar-setup:
    {{python}} -c "from tuttle.eventkit_bridge import _ensure_helper; _ensure_helper()"
    open --wait-apps ~/.tuttle/TuttleCalendar.app --args request-access
    @echo "Check System Settings → Privacy → Calendars for 'Tuttle Calendar'"

# ── Utilities ───────────────────────────────────────────────────────────────

# Install/sync Python dependencies
deps:
    uv sync

# Install Node dependencies
deps-node:
    cd {{electron}} && npm ci

# Install all dependencies
deps-all: deps deps-node

# Reset the demo user data
demo-reset:
    {{python}} -c "from tuttle.app.demo.intent import DemoIntent; DemoIntent().reset(); print('Demo user reset')"
