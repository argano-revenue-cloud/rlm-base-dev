# Demo Tooling

Two scripts and two terminal apps that turn `rlm-base-dev`, a push-button
build system for Salesforce Revenue Cloud orgs, into something you can stand
up and drive in front of an audience without memorizing CumulusCI commands.

**Stack:** CumulusCI · sf CLI · Robot Framework · Textual TUI · Python 3.11+

---

## What the repo builds

`rlm-base-dev` turns the manual work of configuring Salesforce Revenue Cloud, product catalog, pricing, quoting, orders, billing, usage, AI agents, into
version-controlled files. `cumulusci.yml` is the recipe (~30 build steps);
`cci flow run prepare_rlm_org` reads it and produces a fresh, fully-configured
scratch org in 30-60 minutes, unattended, the same way every time.

The demo story: everything on screen was built from files in version control,
not clicked together by hand. `scripts/demo/` is the layer that makes running
that story easy, build the org, then drive a live walkthrough, without
typing raw `cci`/`sf` commands from memory.

## Quick start

Build a fully configured demo org in one command:

```bash
./scripts/demo/run-demo-setup.sh
# checks sf/cci are on PATH, connects the attentis-prod Dev Hub,
# deletes/recreates the "demo" scratch org, runs prepare_rlm_org,
# then opens the org in your browser, 30-60+ min, unattended
```

Prefer clicking through it? Launch the setup TUI instead, same steps, one at
a time or all at once, with a live log and input fields for org alias, Dev
Hub, and admin email:

```bash
./scripts/demo/tui-setup
```

> **Run from a real terminal.** Both TUIs need an interactive TTY (Textual).
> Run them from a local terminal or a VS Code integrated terminal, not
> through a non-interactive IDE tool runner, which will just print "This TUI
> requires an interactive terminal." and exit.

## What's in this folder

| File | Role |
|---|---|
| `run-demo-setup.sh` | Builds the org, end to end: toolchain check → connect Dev Hub → recreate scratch org → `prepare_rlm_org` → open in browser. Safe to re-run, it recreates the named scratch org from scratch each time. |
| `demo-commands.sh` | Not run top-to-bottom, a copy/paste cheat sheet of the commands used *during* a live demo (robot runs, introspection, reset, teardown) plus the talking points for each stage. |
| `tui-setup` | Interactive front-end for `run-demo-setup.sh`. Buttons for each setup step, or "Run all steps," with a streamed log. |
| `tui-demo` | Interactive front-end for `demo-commands.sh`. A menu of live-demo actions with streamed output; destructive ones (rebuild, delete) ask for confirmation first. |
| `tui/common.py` | Shared helpers behind both TUIs: streaming a subprocess into the log, the `docgen:` toggle-and-restore trick, and writing a sanitized scratch-org def with Dev Hub-unsupported features stripped. |
| `tui/_bootstrap.sh` | Launcher both `tui-setup` and `tui-demo` source: creates/reuses a scoped venv at `.harness/demo-tui-venv`, installs `textual` if the requirements hash changed, then runs the app module. |
| `tui/requirements.txt` | Pins the one dependency (`textual>=0.58.0`) used by both TUIs. |
| `script.md` | The narrator's script, plain-English tour of the repo and a suggested demo flow, meant to be read before or during a demo. |

## Running the live demo

Once the org is built, `tui-demo` (or `demo-commands.sh` as a copy/paste
reference) covers everything you'd do live:

```bash
./scripts/demo/tui-demo
# or, headless-scripted equivalents:
cci org browser demo                              # open straight into the app
cci task run robot_e2e --org demo                  # full Quote-to-Order, headless
cci task run robot_e2e_debug \
  -o pause_for_recording true --org demo            # headed, paused for narration
cci task run robot_setup_quote --org demo           # Account -> Opp -> Quote
cci task run robot_order_from_quote --org demo      # Products -> Order -> Activate -> Assets
cci task run robot_reset_account --org demo         # wipe transactional data, re-run clean
```

The Robot Framework suites aren't just tests, they drive a real (optionally
headed) Chrome browser through the app exactly as a presenter would, so
`robot_e2e_debug` doubles as an automated version of the demo you can narrate
over instead of clicking yourself.

## Demo flow

1. **Open the org**, `tui-demo` → "Open org", landing on the Revenue Cloud app.
2. **Product Catalog**, show a configurable bundle; adding an add-on
   triggers constraint-model (CML) rules that require or exclude other
   options automatically.
3. **Build a Quote**, add products; every price is computed live by the
   Revenue Cloud pricing engine (discount tiers, volume pricing), nothing
   hardcoded.
4. **Quote → Order → Activate**, activating creates Assets, Revenue Cloud's
   record of the customer's active subscription and the source of truth for
   renewals, upgrades, and usage.
5. **Billing**, show an invoice generated from the asset's billing schedule;
   if Approvals is on, show an out-of-policy invoice needing sign-off.
6. **Usage**, if the demo data includes usage-based products, show
   consumption tracked and rated against an entitlement.
7. **AI Agents**, ask an Agentforce agent to help build or adjust a quote
   conversationally, same underlying data model as the clicky UI.
8. **The automated version**, `tui-demo` → "Robot E2E, headed + CDP debug,
   paused for narration" runs steps 3-4 for you while you narrate.

## Flags & defaults

```
scripts/demo/run-demo-setup.sh [org-alias] [--skip-docgen] [--admin-email=<email>]
```

| Flag | Behavior |
|---|---|
| `org-alias` | Defaults to `demo`. Used as both the CCI and `sf` alias. |
| `--admin-email` | Scratch org admin email. From `RLM_DEMO_ADMIN_EMAIL` or this flag. Required; no default. |
| `--skip-docgen` | Temporarily flips `docgen: true → false` in `cumulusci.yml` for this run only, then restores it, even on failure (via an `EXIT` trap). See below. |

> **Why `--skip-docgen` exists.** `cci flow run -o` can only set *task*
> options (CCI 4.10 requires the `__` separator), it can't override the
> `project.custom.docgen` flag that gates the Document Generation build
> steps. So skipping docgen means editing the `cumulusci.yml` line directly
> for the run. Reach for this flag if `enable_document_builder_toggle` fails
> to find/verify the Document Builder toggle in headless Chrome, a known
> flake in some sandboxed environments, not as a default.

> **Dev Hub feature gap, handled automatically.** `orgs/dev.json` requests
> the Chatbot (Einstein Bots) feature, which the `attentis-prod` Dev Hub
> isn't licensed for, that would otherwise fail scratch-org creation
> outright. Both the shell script and the setup TUI write a sanitized copy
> under `.harness/scratch-defs/` with the unsupported feature stripped, and
> never touch the original `orgs/dev.json`.

## Common questions

**Is this real data?**
No, it's generated sample data (a fictional product line, "QuantumBit"),
realistic in shape and volume. The pricing, billing, and usage math is real
Salesforce engine calculation, not fake numbers.

**How long does a rebuild take?**
30-60+ minutes, unattended. Run it once before a demo session, not live
during one.

**Does this work on any Salesforce org?**
It targets a fresh scratch org from a Dev Hub. Not every Dev Hub carries
every license this recipe asks for, the tooling already works around the
one gap on `attentis-prod` (Chatbot), so this shouldn't come up, but it's why
a build can fail at the very first "create scratch org" step on an
unfamiliar Dev Hub.

**Something broke mid-demo, now what?**
Reset just the transactional data without rebuilding the whole org:
`tui-demo` → "Robot, Reset Account", or
`cci task run robot_reset_account --org demo`.

**How do the TUIs manage their own dependencies?**
`tui/_bootstrap.sh` creates a scoped venv at `.harness/demo-tui-venv`
(separate from the build-harness TUI's own venv), installs `textual` from
`tui/requirements.txt`, and re-installs only when that file's hash changes.

---

Source: `scripts/demo/` in `rlm-base-dev` · derived from `scripts/demo/script.md`
and the scripts themselves.
