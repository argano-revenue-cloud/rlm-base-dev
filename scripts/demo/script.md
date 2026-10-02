# Demo Script: rlm-base-dev

A plain-English walkthrough of what this repo is, how it works, and what to say
while showing it off. Read this before or during the demo.

---

## 1. The one-line pitch

This repo is a **push-button factory for Salesforce Revenue Cloud orgs**. Run
one command and it builds a complete, fully-configured Salesforce org with a
product catalog, pricing engine, quoting, orders, billing, usage tracking, and
AI agents, all wired together and ready to click through, no manual setup.

Salesforce calls this product **Revenue Cloud** (it used to be called Revenue
Lifecycle Management, or "RLM", that's why so many files still say `rlm`).

## 2. Why this exists

Normally, setting up a Salesforce org with all of Revenue Cloud's features
turned on, catalog, pricing, billing, contracts, partner portal, AI agents, is days of manual clicking in Setup menus. This repo turns that manual process
into **code**: every setting, every sample product, every price rule is a file
in this repo. Running the build reproduces the exact same org every time,
on any Dev Hub, in about 30-60 minutes, unattended.

That's the demo story: *"Everything you're about to see was built from files
in version control, not clicked together by hand."*

## 3. How it works, in one picture

```
   orgs/dev.json              cumulusci.yml               (this repo's code)
  (org shape/features)    (the build recipe: ~30 steps)
        │                          │
        └──────────┬───────────────┘
                    ▼
         "cci flow run prepare_rlm_org"
                    │
                    ▼
      a brand-new Salesforce scratch org, fully built:
      product catalog + pricing + quoting + orders +
      billing + usage + AI agents + all the UI
```

- **CumulusCI** ("cci") is the engine that reads the recipe and does the work.
  Think of it as a build tool for Salesforce, the same way you'd use a CI
  pipeline to build and deploy a web app.
- **The recipe** is `cumulusci.yml`, one very large file that lists every
  step of the build (deploy this metadata, load this sample data, turn on
  this setting, run this test) and every feature flag that turns pieces on
  or off.
- **The org** it produces is a Salesforce "scratch org", a temporary,
  disposable Salesforce environment, created fresh from a Dev Hub, that
  expires after 30 days. Nothing is shared between demo runs unless you want
  it to be.

## 4. Component-by-component tour

### `cumulusci.yml`, the recipe book
The single most important file. It defines:
- **Scratch org shapes** (`orgs:` section), which Salesforce features a new
  org should have (Billing? Partner Community? AI Agents?).
- **Feature flags** (`project.custom`), on/off switches like `billing`,
  `docgen`, `agents`, `prm` that turn whole subsystems on or off during the
  build.
- **Flows**, named sequences of steps. The one you'll use most is
  `prepare_rlm_org`, the "build the whole org" flow (about 30 steps).
- **Tasks**, the individual building blocks a flow is made of (deploy this
  folder, run this Python script, load this data file).

### `orgs/`, org shapes
JSON files describing what a *type* of org should look like: Developer
Edition vs Enterprise Edition, which Salesforce features/licenses it needs
(Billing, Partner Community, Order Management, AI Platform, etc). `dev.json`
is the one used for demos.

### `force-app/`, `templates/`, `unpackaged/`, the actual Salesforce metadata
This is the Salesforce "stuff" itself: objects, fields, page layouts, flows,
permission sets, flexipages (the screens users see). It's split into layers:
- `force-app/`, the core, always-deployed metadata.
- `templates/`, reusable page/layout templates that get assembled
  differently depending on which features are turned on (a demo org with
  Billing on gets different Home page tiles than one without it).
- `unpackaged/`, metadata that's *conditionally* deployed based on the
  feature flags above (e.g. `unpackaged/post_billing/` only deploys if
  `billing: true`).

### `datasets/`, the sample data
Nothing in the demo is empty, every product, price, customer, and contract
you see comes from here:
- `datasets/sfdmu/`, bulk sample data (products, prices, accounts) loaded
  with a tool called SFDMU (Salesforce Data Move Utility).
- `datasets/constraints/`, "CML" rule files: the logic behind configurable
  bundles (e.g. "you can't select this add-on without that base product").
- `datasets/context_plans/`, small data patches applied after the main load.

### `tasks/`, custom automation
Python scripts that do things beyond a simple metadata deploy: activate
decision tables, repair pricing schedules, manage constraint models, clean up
settings that don't exist in every org type. These are the "glue" that makes
the build idempotent (safe to re-run) and self-healing.

### `robot/`, automated browser tests
Robot Framework scripts that literally drive a (headless) Chrome browser
through the app, the same way a person would: log in, create an opportunity,
build a quote, add products, place an order, activate it, and check the
resulting subscription (asset) shows up. This doubles as **an automated demo
you can play back**, see Section 5.

### `scripts/`, everything else
Helper scripts: data transformations, validation, and (new) the demo tooling
in `scripts/demo/` described below.

### `docs/`, deeper documentation
Setup guides, feature design docs, and references for anyone extending the
repo. Not needed for the demo itself, but good to point to if someone asks
"how do I add a new feature to this?"

## 5. The demo tooling (`scripts/demo/`)

Built specifically to make running this demo easy, without memorizing CLI
commands:

| File | What it does |
|---|---|
| `run-demo-setup.sh` | One command, builds the whole org from scratch: checks your toolchain, connects the Dev Hub, creates the scratch org, runs the full build, opens the org in your browser. |
| `demo-commands.sh` | A cheat sheet of commands to run *during* the live demo (see below). |
| `tui-setup` | An interactive terminal app (menu with buttons) for the setup steps above, click through them one at a time, or "Run all steps," and watch the live log. |
| `tui-demo` | An interactive terminal app (menu with buttons) for the live-demo commands, Quote-to-Order run, reset the demo data, open the org, etc. |

Run `./scripts/demo/tui-setup` or `./scripts/demo/tui-demo` from a real
terminal (not through an IDE's non-interactive tool) to get the full-screen
menu.

## 6. Suggested demo flow

1. **Open the org** (`tui-demo` → "Open org", or `cci org browser <alias>`).
   Land on the Revenue Cloud app.
2. **Product Catalog**, show a configurable bundle. Point out that adding
   an add-on can trigger rules (constraint model / CML) that require or
   exclude other options automatically.
3. **Build a Quote**, add products, and call out that every price shown is
   computed live by the Revenue Cloud pricing engine (discount tiers,
   volume pricing), nothing is hardcoded.
4. **Quote → Order → Activate**, turn the quote into an order and activate
   it. This creates **Assets**, which is Revenue Cloud's word for "the
   customer's active subscription." Assets are the source of truth for
   everything that happens next: renewals, upgrades/downgrades, usage.
5. **Billing**, show an invoice being generated from the billing schedule
   tied to that asset. If Approvals is on, show an out-of-policy invoice
   needing sign-off.
6. **Usage**, if the demo data includes usage-based products, show
   consumption being tracked and rated against an entitlement.
7. **AI Agents**, ask an Agentforce agent (if `agents: true`) to help build
   or adjust a quote conversationally, showing that the same underlying data
   model powers both the clicky UI and the AI assistant.
8. **The automated version**: run `tui-demo` → "Robot E2E, headed + CDP
   debug, paused for narration" to have the browser perform steps 3-4
   automatically while you narrate, instead of clicking yourself.

## 7. Things worth knowing if someone asks a hard question

- **"Is this real data?"** No, it's generated sample data (a fictional
  product line called "QuantumBit"), but it's realistic in shape and volume,
  and the pricing/billing/usage math is 100% real Salesforce engine
  calculation, not fake numbers.
- **"How long does a rebuild take?"** 30-60+ minutes for a full build,
  unattended. It's meant to run once before a demo session, not live during
  one.
- **"Does this work on any Salesforce org?"** It targets a fresh scratch org
  from a Dev Hub. Not every Dev Hub has every Salesforce license/feature
  this recipe asks for (for example, some Dev Hubs aren't licensed for the
  Einstein Bots/"Chatbot" feature), the demo tooling in `scripts/demo/`
  already works around the one gap we hit on our own Dev Hub, so this
  shouldn't come up, but it's worth knowing why if a build ever fails at
  the very first "create scratch org" step.
- **"What if something in the live demo breaks?"** Reset just the
  transactional data without rebuilding the whole org: `tui-demo` →
  "Robot, Reset Account."
