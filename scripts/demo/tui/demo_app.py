"""Textual TUI for scripts/demo/demo-commands.sh.

A menu of the same commands that cheat sheet documents — Quote-to-Order robot
runs, modular robot steps, org introspection, and org lifecycle — each run
live with streamed output. Destructive actions (rebuild, delete) ask for
confirmation first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog, Static

from scripts.demo.tui.common import REPO_ROOT, run_streamed

DEFAULT_ORG_ALIAS = "demo"
DEFAULT_ADMIN_EMAIL = os.environ.get("RLM_DEMO_ADMIN_EMAIL", "")


@dataclass(frozen=True)
class Action:
    """One demo command."""

    label: str
    build_cmd: Callable[[str, bool, str], list[str]]
    destructive: bool = False
    confirm_message: str = ""


ACTIONS: dict[str, Action] = {
    "open": Action("Open org", lambda alias, skip_docgen, email: ["cci", "org", "browser", alias]),
    "e2e": Action(
        "Robot E2E — full Quote-to-Order (headless)",
        lambda alias, skip_docgen, email: ["cci", "task", "run", "robot_e2e", "--org", alias],
    ),
    "e2e_debug": Action(
        "Robot E2E — headed + CDP debug, paused for narration",
        lambda alias, skip_docgen, email: [
            "cci", "task", "run", "robot_e2e_debug", "-o", "pause_for_recording", "true", "--org", alias,
        ],
    ),
    "setup_quote": Action(
        "Robot — Setup Quote only (Account -> Opp -> Quote)",
        lambda alias, skip_docgen, email: ["cci", "task", "run", "robot_setup_quote", "--org", alias],
    ),
    "order_from_quote": Action(
        "Robot — Order From Quote only (Products -> Order -> Activate -> Assets)",
        lambda alias, skip_docgen, email: ["cci", "task", "run", "robot_order_from_quote", "--org", alias],
    ),
    "reset_account": Action(
        "Robot — Reset Account (clear transactional data)",
        lambda alias, skip_docgen, email: ["cci", "task", "run", "robot_reset_account", "--org", alias],
    ),
    "decision_tables": Action(
        "List decision tables",
        lambda alias, skip_docgen, email: [
            "cci", "task", "run", "manage_decision_tables", "--operation", "list", "--org", alias,
        ],
    ),
    "expression_sets": Action(
        "List expression sets (constraint models)",
        lambda alias, skip_docgen, email: [
            "cci", "task", "run", "manage_expression_sets", "--operation", "list", "--org", alias,
        ],
    ),
    "flow_info": Action(
        "Show prepare_rlm_org flow info",
        lambda alias, skip_docgen, email: ["cci", "flow", "info", "prepare_rlm_org"],
    ),
    "rebuild": Action(
        "Rebuild org from scratch (full run-demo-setup.sh)",
        lambda alias, skip_docgen, email: [
            str(REPO_ROOT / "scripts" / "demo" / "run-demo-setup.sh"),
            alias,
            f"--admin-email={email}",
            *(["--skip-docgen"] if skip_docgen else []),
        ],
        destructive=True,
        confirm_message="This deletes and recreates the scratch org, then re-runs the full build. Continue?",
    ),
    "delete": Action(
        "Delete scratch org",
        lambda alias, skip_docgen, email: ["cci", "org", "scratch_delete", alias],
        destructive=True,
        confirm_message="This permanently deletes the scratch org. Continue?",
    ),
}


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation gate for destructive actions."""

    CSS = """
    ConfirmScreen { align: center middle; }
    #dialog {
        width: 60; height: auto; border: thick $error;
        padding: 1 2; background: $surface;
    }
    #dialog Button { margin-top: 1; margin-right: 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message)
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Confirm", id="confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class DemoApp(App):
    """Menu of live-demo commands for an already-built rlm-base-dev org."""

    TITLE = "rlm-base-dev — demo commands"
    CSS = """
    #controls { height: auto; padding: 1; }
    #inputs { height: auto; margin-bottom: 1; }
    #inputs Input { width: 30; margin-right: 2; }
    #buttons { height: auto; }
    #buttons Button { width: 100%; margin-bottom: 1; }
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
                yield Label("Admin email:")
                yield Input(value=DEFAULT_ADMIN_EMAIL, id="admin_email")
            yield Checkbox(
                "On rebuild, skip Document Generation (docgen) — works around "
                "enable_document_builder_toggle failing to verify the toggle "
                "in headless Chrome/Chromium",
                id="skip_docgen",
            )
            with Vertical(id="buttons"):
                for action_id, action in ACTIONS.items():
                    variant = "error" if action.destructive else "default"
                    yield Button(action.label, id=action_id, variant=variant)
            yield Static("Idle.", id="status")
        yield RichLog(id="log", highlight=True, markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.log_line(f"repo: {REPO_ROOT}")
        self.log_line("Pick a command to run against the org above.")

    # -- widget helpers -------------------------------------------------------

    def org_alias(self) -> str:
        return self.query_one("#org_alias", Input).value.strip() or DEFAULT_ORG_ALIAS

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = ACTIONS.get(event.button.id or "")
        if action is None:
            return
        if action.destructive:
            self.push_screen(ConfirmScreen(action.confirm_message), lambda confirmed: self._maybe_run(action, confirmed))
        else:
            self._maybe_run(action, True)

    def _maybe_run(self, action: Action, confirmed: bool) -> None:
        if confirmed:
            self.run_action_cmd(action)

    @work(exclusive=True, thread=True)
    def run_action_cmd(self, action: Action) -> None:
        cmd = action.build_cmd(self.org_alias(), self.skip_docgen(), self.admin_email())
        self.call_from_thread(self.set_buttons_enabled, False)
        self.call_from_thread(self.set_status, action.label)
        self.call_from_thread(self.log_line, f"$ {' '.join(cmd)}")
        code = run_streamed(cmd, lambda line: self.call_from_thread(self.log_line, line))
        status = "Done." if code == 0 else f"Failed (exit {code})."
        self.call_from_thread(self.set_status, status)
        self.call_from_thread(self.set_buttons_enabled, True)


if __name__ == "__main__":
    DemoApp().run()
