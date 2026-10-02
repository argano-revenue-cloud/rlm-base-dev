"""Textual TUI for scripts/demo/run-demo-setup.sh.

Interactive front-end for building a demo scratch org: validate the local
toolchain, connect the Dev Hub, (re)create the scratch org, run the full
prepare_rlm_org build, and open the org — each as its own button, or all in
sequence via "Run all steps".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog, Static

from scripts.demo.tui.common import REPO_ROOT, prepare_scratch_def, run_streamed, set_docgen_enabled

DEFAULT_ORG_ALIAS = "demo"
DEFAULT_DEVHUB_ALIAS = os.environ.get("RLM_DEMO_DEVHUB", "")
DEFAULT_ADMIN_EMAIL = os.environ.get("RLM_DEMO_ADMIN_EMAIL", "")
SCRATCH_CONFIG_NAME = "dev"


@dataclass(frozen=True)
class Step:
    """One command in a setup sequence."""

    description: str
    cmd: list[str]
    allow_fail: bool = False


class SetupApp(App):
    """Build a fully configured Revenue Cloud scratch org from this repo."""

    TITLE = "rlm-base-dev — demo org setup"
    CSS = """
    #controls { height: auto; padding: 1; }
    #inputs { height: auto; margin-bottom: 1; }
    #inputs Input { width: 30; margin-right: 2; }
    #buttons { height: auto; }
    #buttons Button { margin-right: 1; margin-bottom: 1; }
    #status { padding: 0 1; color: $text-muted; }
    RichLog { border: solid $accent; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="controls"):
            with Horizontal(id="inputs"):
                yield Label("Org alias:")
                yield Input(value=DEFAULT_ORG_ALIAS, id="org_alias")
                yield Label("Dev Hub alias:")
                yield Input(value=DEFAULT_DEVHUB_ALIAS, id="devhub_alias")
                yield Label("Admin email:")
                yield Input(value=DEFAULT_ADMIN_EMAIL, id="admin_email")
            yield Checkbox(
                "Skip Document Generation (docgen) — works around "
                "enable_document_builder_toggle failing to verify the toggle "
                "in headless Chrome/Chromium",
                id="skip_docgen",
            )
            with Horizontal(id="buttons"):
                yield Button("1. Validate setup", id="validate")
                yield Button("2. Connect Dev Hub", id="devhub")
                yield Button("3. Recreate scratch org", id="recreate")
                yield Button("4. Run full build", id="build", variant="warning")
                yield Button("5. Open org", id="open")
                yield Button("Run all steps", id="all", variant="success")
            yield Static("Idle.", id="status")
        yield RichLog(id="log", highlight=True, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.log_line(f"repo: {REPO_ROOT}")
        self.log_line("Pick a step, or 'Run all steps' for the full build.")

    # -- widget helpers -----------------------------------------------------

    def org_alias(self) -> str:
        return self.query_one("#org_alias", Input).value.strip() or DEFAULT_ORG_ALIAS

    def devhub_alias(self) -> str:
        return self.query_one("#devhub_alias", Input).value.strip() or DEFAULT_DEVHUB_ALIAS

    def admin_email(self) -> str:
        return self.query_one("#admin_email", Input).value.strip() or DEFAULT_ADMIN_EMAIL

    def skip_docgen(self) -> bool:
        return self.query_one("#skip_docgen", Checkbox).value

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def set_buttons_enabled(self, enabled: bool) -> None:
        for button in self.query(Button):
            button.disabled = not enabled

    def log_line(self, line: str) -> None:
        self.query_one("#log", RichLog).write(line)

    # -- step definitions -----------------------------------------------------

    def _step_validate(self) -> Step:
        return Step("Validating local toolchain...", ["cci", "task", "run", "validate_setup"])

    def _step_devhub(self) -> Step:
        alias = self.devhub_alias()
        return Step(
            f"Connecting Dev Hub '{alias}'...",
            ["cci", "service", "connect", "devhub", alias, "--username", alias, "--default"],
        )

    def _step_delete(self) -> Step:
        alias = self.org_alias()
        return Step(
            f"Deleting any existing scratch org '{alias}'...",
            ["cci", "org", "scratch_delete", alias],
            allow_fail=True,  # no-op the first time the alias is used
        )

    def _step_create(self) -> Step:
        # `cci org scratch dev <alias>` calls `sf org create scratch -f orgs/dev.json`
        # verbatim, with no flag to strip a feature the Dev Hub isn't licensed
        # for (e.g. attentis-prod + Chatbot). Create directly from a sanitized
        # config instead so the Dev Hub's known license gaps don't fail the
        # whole org creation (see common.prepare_scratch_def).
        alias = self.org_alias()
        devhub = self.devhub_alias()
        email = self.admin_email()
        sanitized_path, excluded = prepare_scratch_def(SCRATCH_CONFIG_NAME, devhub)
        if excluded:
            self.log_line(
                f"orgs/{SCRATCH_CONFIG_NAME}.json: stripped unsupported features for "
                f"'{devhub}': {', '.join(excluded)}"
            )
        return Step(
            f"Creating scratch org '{alias}' (admin: {email})...",
            [
                "sf", "org", "create", "scratch",
                "-f", str(sanitized_path),
                "-w", "15",
                "--target-dev-hub", devhub,
                "--no-namespace",
                "--duration-days", "30",
                "-a", alias,  # sf CLI alias == the org alias typed above, nothing added
                f"--admin-email={email}",
                "--set-default",
            ],
        )

    def _step_import(self) -> Step:
        alias = self.org_alias()
        return Step(
            f"Registering '{alias}' in the CumulusCI keychain...",
            ["cci", "org", "import", alias, alias],
        )

    def _step_build(self) -> Step:
        alias = self.org_alias()
        description = f"Running prepare_rlm_org on '{alias}' (30-60+ min)..."
        if self.skip_docgen():
            description += " [docgen temporarily disabled]"
        return Step(description, ["cci", "flow", "run", "prepare_rlm_org", "--org", alias])

    def _step_open(self) -> Step:
        alias = self.org_alias()
        return Step(f"Opening '{alias}' in the browser...", ["cci", "org", "browser", alias])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        sequences: dict[str, Callable[[], list[Step]]] = {
            "validate": lambda: [self._step_validate()],
            "devhub": lambda: [self._step_devhub()],
            "recreate": lambda: [self._step_delete(), self._step_create(), self._step_import()],
            "build": lambda: [self._step_build()],
            "open": lambda: [self._step_open()],
            "all": lambda: [
                self._step_validate(),
                self._step_devhub(),
                self._step_delete(),
                self._step_create(),
                self._step_import(),
                self._step_build(),
                self._step_open(),
            ],
        }
        build_steps = sequences.get(event.button.id or "")
        if build_steps is not None:
            self.run_steps(build_steps())

    def _toggle_docgen(self, enabled: bool) -> None:
        ok = set_docgen_enabled(enabled)
        if ok:
            self.call_from_thread(self.log_line, f"cumulusci.yml: docgen -> {str(enabled).lower()}")
        else:
            self.call_from_thread(
                self.log_line,
                "WARNING: expected `docgen:` line not found verbatim in cumulusci.yml; left untouched.",
            )

    @work(exclusive=True, thread=True)
    def run_steps(self, steps: list[Step]) -> None:
        self.call_from_thread(self.set_buttons_enabled, False)
        skip_docgen = self.skip_docgen()
        if skip_docgen:
            self._toggle_docgen(enabled=False)
        try:
            for step in steps:
                self.call_from_thread(self.set_status, step.description)
                self.call_from_thread(self.log_line, f"$ {' '.join(step.cmd)}")
                code = run_streamed(step.cmd, lambda line: self.call_from_thread(self.log_line, line))
                if code != 0 and not step.allow_fail:
                    self.call_from_thread(self.set_status, f"Failed (exit {code}): {step.description}")
                    return
            self.call_from_thread(self.set_status, "Done.")
        finally:
            if skip_docgen:
                self._toggle_docgen(enabled=True)
            self.call_from_thread(self.set_buttons_enabled, True)


if __name__ == "__main__":
    SetupApp().run()
