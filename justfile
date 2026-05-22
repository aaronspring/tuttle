# Tuttle – development & build tasks

set dotenv-load := false

repo     := justfile_directory()
electron := repo / "ui"
venv     := repo / ".venv"
python   := venv / "bin/python"
app      := electron / "release/mac-arm64/Tuttle.app"

# ── Development ─────────────────────────────────────────────────────────────

# Electron + Vite dev server (hot reload, live Python from .venv)
# vite-plugin-electron auto-launches Electron when Vite starts in dev mode.
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{electron}}"
    npm run build
    VITE_DEV_SERVER_URL=http://localhost:5173 npx vite

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

# Wipe all app data and start fresh (dev only)
reset:
    rm -rf ~/.tuttle
    @echo "✓ ~/.tuttle removed – next launch will recreate everything from scratch"

# ── Release ─────────────────────────────────────────────────────────────────

# Bump version, commit, tag, push to origin, create GitHub release.
#
#   just release patch                  3.1.0 → 3.1.1
#   just release minor                  3.1.0 → 3.2.0
#   just release major                  3.1.0 → 4.0.0
#   just release minor --pre a          3.1.0 → 3.2.0a1   (alpha)
#   just release patch --pre rc         3.1.0 → 3.1.1rc1  (release candidate)
#
# Add --dry-run to preview without changing anything.
release part *flags="":
    #!/usr/bin/env bash
    set -euo pipefail
    dry_run=0
    pre=""
    bump_flags=()
    for arg in {{flags}}; do
        if [[ "$arg" == "--pre" ]]; then pre="next"; continue; fi
        if [[ "$pre" == "next" ]]; then pre="$arg"; continue; fi
        if [[ "$arg" == "--dry-run" ]]; then dry_run=1; fi
        bump_flags+=("$arg")
    done
    if [[ -n "$pre" && "$pre" != "next" ]]; then
        base=$({{python}} -m bumpversion show new_version --increment {{part}})
        bump_flags+=(--new-version "${base}${pre}1")
    fi
    {{python}} -m bumpversion bump {{part}} "${bump_flags[@]}"
    if [[ "$dry_run" -eq 1 ]]; then exit 0; fi
    tag=$(git describe --tags --abbrev=0)
    git push origin main
    git push origin "$tag"
    gh_flags=(--generate-notes)
    if [[ "$tag" == *a* || "$tag" == *b* || "$tag" == *rc* ]]; then
        gh_flags+=(--prerelease)
    fi
    gh release create "$tag" "${gh_flags[@]}"
