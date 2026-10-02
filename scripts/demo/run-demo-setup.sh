#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rlm-base-dev demo bootstrap
#
# Builds a fully configured Revenue Cloud scratch org from this repo using
# attentis-prod as the Dev Hub, then prints the commands to run a live demo
# (Quote-to-Order flow, billing, agents, etc).
#
# Usage:
#   scripts/demo/run-demo-setup.sh [org-alias] [--skip-docgen] [--admin-email=<email>]
#
# --admin-email sets the scratch org's admin email (or RLM_DEMO_ADMIN_EMAIL). Required.
# RLM_DEMO_DEVHUB names the Dev Hub alias. Required.
#
# --skip-docgen disables the Document Generation subsystem for this run
# (unpackaged/pre_docgen + post_docgen, and the enable_document_builder_toggle
# Robot task). Use it if that Robot task fails to find/verify the Document
# Builder toggle in headless Chrome/Chromium — a known flake in some
# sandboxed environments.
#
# NOTE: `cci flow run -o` only sets *task* options (`task__option` — CCI
# 4.10 rejects anything without `__`, see cumulusci.cli.flow.flow_run). It
# cannot override `project.custom.docgen`, which is what prepare_docgen's
# `when:` step conditions actually read. So --skip-docgen instead flips the
# `docgen:` line in cumulusci.yml before the run and restores it after (even
# on failure/interrupt, via the EXIT trap below) — same trick the demo TUIs
# use from Python (scripts/demo/tui/common.py: set_docgen_enabled).
#
# Safe to re-run: recreates the named scratch org from scratch each time.
# ---------------------------------------------------------------------------
set -euo pipefail

ORG_ALIAS="demo"
SKIP_DOCGEN=0
ADMIN_EMAIL="${RLM_DEMO_ADMIN_EMAIL:-}"
for arg in "$@"; do
  case "$arg" in
    --skip-docgen) SKIP_DOCGEN=1 ;;
    --admin-email=*) ADMIN_EMAIL="${arg#--admin-email=}" ;;
    *) ORG_ALIAS="$arg" ;;
  esac
done
DEVHUB_ALIAS="${RLM_DEMO_DEVHUB:-}"
[ -n "$DEVHUB_ALIAS" ] || { echo "Set RLM_DEMO_DEVHUB to your Dev Hub alias (sf org login web --alias <hub>)."; exit 1; }
[ -n "$ADMIN_EMAIL" ] || { echo "Set RLM_DEMO_ADMIN_EMAIL or pass --admin-email=<email>."; exit 1; }
SCRATCH_CONFIG_NAME="dev"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$REPO_ROOT"

# sf CLI (May 2026+) redacts access tokens from --json output by default.
# CumulusCI still needs the raw token to build its keychain auth headers.
export SF_TEMP_SHOW_SECRETS=true

# Flip the `docgen:` custom flag in cumulusci.yml in place (see NOTE above).
# $1 = true|false. No-ops (with a warning) if the line isn't found verbatim,
# rather than guessing at a different edit.
set_docgen() {
  python3 - "$1" <<'PYEOF'
import re
import sys
from pathlib import Path

enabled = sys.argv[1]
path = Path("cumulusci.yml")
text = path.read_text()
pattern = re.compile(r"^(?P<indent>\s*docgen:\s*)(?P<value>true|false)(?P<rest>\s*#.*)?$", re.MULTILINE)
match = pattern.search(text)
if match is None:
    print("WARNING: expected `docgen:` line not found verbatim in cumulusci.yml; left untouched.")
    sys.exit(0)
if match.group("value") != enabled:
    new_line = f"{match.group('indent')}{enabled}{match.group('rest') or ''}"
    path.write_text(text[: match.start()] + new_line + text[match.end():])
print(f"cumulusci.yml: docgen -> {enabled}")
PYEOF
}

# `cci org scratch <config> <alias>` calls `sf org create scratch -f orgs/<config>.json`
# verbatim (see `cci org scratch --help`), with no flag to strip a feature the
# Dev Hub isn't licensed for. attentis-prod lacks Chatbot (Einstein Bots),
# which makes orgs/dev.json's request fail outright ("Chatbot is not a valid
# Features value.") instead of a partial/degraded org. Write a sanitized copy
# (never touching the original — other Dev Hubs may have every feature it
# asks for); the sf CLI alias is the org alias itself, nothing appended (see
# scripts/demo/tui/common.py: prepare_scratch_def, same trick from Python).
prepare_scratch_def() {
  python3 - "$SCRATCH_CONFIG_NAME" "$DEVHUB_ALIAS" <<'PYEOF'
import json
import sys
from pathlib import Path

config_name, devhub = sys.argv[1], sys.argv[2]
UNSUPPORTED_FEATURES_BY_DEVHUB = {
    # Dev Hubs known to lack a feature that orgs/dev.json requests. Add yours after a failed create.
    "attentis-prod": ("Chatbot",),
    "csg-prod": ("Chatbot",),
}
src = Path("orgs") / f"{config_name}.json"
data = json.loads(src.read_text())
excluded = list(UNSUPPORTED_FEATURES_BY_DEVHUB.get(devhub, ()))
if excluded:
    data["features"] = [f for f in data.get("features", []) if f not in excluded]
    print(f"   (stripped unsupported features for '{devhub}': {', '.join(excluded)})", file=sys.stderr)
out_dir = Path(".harness/scratch-defs")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{config_name}.{devhub}.json"
out_path.write_text(json.dumps(data, indent=2))
print(out_path)  # stdout only: captured by the caller as $(prepare_scratch_def)
PYEOF
}

echo "== 1. Toolchain check =="
command -v sf  >/dev/null || { echo "sf CLI not found on PATH"; exit 1; }
command -v cci >/dev/null || { echo "cci not found on PATH (pipx install cumulusci)"; exit 1; }
cci task run validate_setup

echo "== 2. Point CumulusCI at the Dev Hub =="
# One-time per machine; harmless to re-run.
sf org list --json >/dev/null 2>&1 || true
if ! sf org display --target-org "$DEVHUB_ALIAS" >/dev/null 2>&1; then
  echo "Dev Hub '$DEVHUB_ALIAS' isn't authenticated with sf yet."
  echo "Run:  sf org login web --alias $DEVHUB_ALIAS --instance-url https://login.salesforce.com"
  exit 1
fi
cci service connect devhub "$DEVHUB_ALIAS" --username "$DEVHUB_ALIAS" --default

echo "== 3. Recreate the scratch org (admin: $ADMIN_EMAIL) =="
cci org scratch_delete "$ORG_ALIAS" 2>/dev/null || true
SANITIZED_DEF="$(prepare_scratch_def)"
sf org create scratch -f "$SANITIZED_DEF" -w 15 \
  --target-dev-hub "$DEVHUB_ALIAS" --no-namespace --duration-days 30 \
  -a "$ORG_ALIAS" --admin-email="$ADMIN_EMAIL" --set-default
cci org import "$ORG_ALIAS" "$ORG_ALIAS"

echo "== 4. Run the full Revenue Cloud build (prepare_rlm_org) =="
echo "   This deploys product catalog, pricing, billing, agents, doc-gen,"
echo "   constraints, PRM, CLM, and UX — expect ~30-60+ minutes."
if [[ "$SKIP_DOCGEN" -eq 1 ]]; then
  echo "   (--skip-docgen: temporarily disabling docgen in cumulusci.yml for this run)"
  set_docgen false
  trap 'set_docgen true' EXIT
fi
cci flow run prepare_rlm_org --org "$ORG_ALIAS"

echo "== 5. Open the org =="
cci org browser "$ORG_ALIAS"

cat <<EOF

===========================================================================
Org '$ORG_ALIAS' is built. See scripts/demo/demo-commands.sh for the
commands to drive a live demo (Quote-to-Order, billing, catalog, agents).
===========================================================================
EOF
