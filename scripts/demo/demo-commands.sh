#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rlm-base-dev — demo command cheat sheet
#
# This is not meant to be run top-to-bottom unattended: it's a reference of
# the commands used to drive a live Revenue Cloud demo once the org built by
# run-demo-setup.sh is ready. Copy/paste sections as needed.
#
# Prereqs: scripts/demo/run-demo-setup.sh already ran successfully.
# ---------------------------------------------------------------------------
set -euo pipefail

ORG_ALIAS="${1:-demo}"
export SF_TEMP_SHOW_SECRETS=true
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ── Open the org straight into the Revenue Cloud app ───────────────────────
cci org browser "$ORG_ALIAS"

# ── Automated live demo: headless Chrome runs the whole Quote-to-Order flow
#    (Reset Account -> Opportunity -> Quote -> Browse Catalog -> Add Product
#    -> Save Quote -> Create Order -> Activate -> Verify Assets) and drops a
#    log.html/report.html + screenshots under robot/rlm-base/results/. ─────
cci task run robot_e2e --org "$ORG_ALIAS"

# ── Same flow, but headed + paused at key points so you can narrate live in
#    front of an audience (Chrome DevTools Protocol on port 9222) ─────────
cci task run robot_e2e_debug -o pause_for_recording true --org "$ORG_ALIAS"

# ── Modular variants, if you want to demo just one half ────────────────────
cci task run robot_setup_quote --org "$ORG_ALIAS"       # Account -> Opp -> Quote
cci task run robot_order_from_quote --org "$ORG_ALIAS"  # Add products -> Order -> Activate -> Assets
cci task run robot_reset_account --org "$ORG_ALIAS"      # wipe transactional data, re-run clean

# ── Talking points while the org is open ────────────────────────────────────
# 1. Product Catalog (QuantumBit dataset)  -> configurable bundles, attributes,
#    constraint rules (CML) that drive dynamic pricing/eligibility.
# 2. Quote -> real-time price waterfall (discounts, tiers, ramps) computed by
#    the RC pricing engine, not client-side math.
# 3. Quote -> Order -> Activate -> Assets: the RLM lifecycle (subscription
#    assets are the source of truth for renewals/amendments/usage).
# 4. Billing tab: BillingScheduleGroup/BillingSchedule -> Invoice runs,
#    Invoice Approval, Credits/Debits, Usage-based rating.
# 5. Agentforce: agent actions wired to the same Apex/Flow invocables (agents
#    flag in cumulusci.yml) — ask an agent to build/adjust a quote.
# 6. Partner/Customer Experience: PRM community + Self-Service Billing Portal
#    (billing_portal flag) if you want to show the customer-facing side.

# ── Inspect what got built (useful while narrating "what did this deploy") ─
cci flow info prepare_rlm_org
cci task run manage_decision_tables --operation list --org "$ORG_ALIAS"
cci task run manage_expression_sets --operation list --org "$ORG_ALIAS"

# ── Reset for a repeat demo without rebuilding the whole org ───────────────
cci task run robot_reset_account --org "$ORG_ALIAS"

# ── Full rebuild from scratch (new scratch org + full flow) ────────────────
# scripts/demo/run-demo-setup.sh "$ORG_ALIAS"
# If enable_document_builder_toggle fails to find/verify the Document Builder
# toggle in headless Chrome/Chromium (known flake in some sandboxed
# environments), rebuild with Document Generation skipped instead:
# scripts/demo/run-demo-setup.sh "$ORG_ALIAS" --skip-docgen

# ── Tear down when done ─────────────────────────────────────────────────────
# cci org scratch_delete "$ORG_ALIAS"
