"""Shared helpers for the scripts/demo Textual TUIs (setup_app, demo_app)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]

_DOCGEN_LINE = re.compile(r"^(?P<indent>\s*docgen:\s*)(?P<value>true|false)(?P<rest>\s*#.*)?$", re.MULTILINE)

# `cci org scratch <config> <alias>` runs `sf org create scratch -f orgs/<config>.json`
# verbatim (see `cci org scratch --help`) with no flag to strip individual
# features. Some Dev Hubs aren't licensed for everything a scratch config
# requests — attentis-prod lacks Chatbot (Einstein Bots), which makes scratch
# creation fail outright ("Chatbot is not a valid Features value.") instead
# of a partial/degraded org. Keyed by Dev Hub alias so this stays correct if
# the script/TUI is later pointed at a different org that has no such gap.
UNSUPPORTED_FEATURES_BY_DEVHUB: dict[str, tuple[str, ...]] = {
    "attentis-prod": ("Chatbot",),
    "csg-prod": ("Chatbot",),
}


def demo_env() -> dict:
    """Environment for sf/cci subprocesses.

    Adds the token-redaction opt-out CumulusCI needs to read scratch org auth
    (see .envrc: sf >= May-2026 redacts access tokens from --json output by
    default, which breaks CCI's keychain auth unless this is set).
    """
    env = os.environ.copy()
    env["SF_TEMP_SHOW_SECRETS"] = "true"
    return env


def set_docgen_enabled(enabled: bool) -> bool:
    """Toggle the `docgen` custom flag directly in cumulusci.yml.

    CumulusCI 4.10's `cci flow run -o` only sets task options (`task__option`
    — see `cumulusci.cli.flow.flow_run`, which rejects anything without
    `__`); it cannot override the `project.custom.docgen` value that the
    prepare_docgen flow's `when:` step conditions read. So skipping docgen
    for one run means flipping this line in cumulusci.yml before the run and
    flipping it back after (see scripts/demo/run-demo-setup.sh's --skip-docgen
    for the same trick from bash).

    Returns True if the file is now in the requested state (changed or
    already there), False if the expected `docgen:` line wasn't found —
    left untouched rather than guessing.
    """
    yml_path = REPO_ROOT / "cumulusci.yml"
    text = yml_path.read_text()
    match = _DOCGEN_LINE.search(text)
    if match is None:
        return False
    new_value = "true" if enabled else "false"
    if match.group("value") == new_value:
        return True
    new_line = f"{match.group('indent')}{new_value}{match.group('rest') or ''}"
    yml_path.write_text(text[: match.start()] + new_line + text[match.end() :])
    return True


def prepare_scratch_def(config_name: str, devhub_alias: str) -> tuple[Path, list[str]]:
    """Write a sanitized copy of orgs/<config_name>.json with any features
    unsupported by `devhub_alias` stripped out (see UNSUPPORTED_FEATURES_BY_DEVHUB).

    The original orgs/<config_name>.json is never modified — other Dev Hubs
    using this repo may well have every feature it requests. Returns the
    sanitized file's path and the list of features that were removed (empty
    if none needed removing).
    """
    src = REPO_ROOT / "orgs" / f"{config_name}.json"
    data = json.loads(src.read_text())
    excluded = list(UNSUPPORTED_FEATURES_BY_DEVHUB.get(devhub_alias, ()))
    if excluded:
        data["features"] = [f for f in data.get("features", []) if f not in excluded]
    out_dir = REPO_ROOT / ".harness" / "scratch-defs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{config_name}.{devhub_alias}.json"
    out_path.write_text(json.dumps(data, indent=2))
    return out_path, excluded


def run_streamed(cmd: Sequence[str], on_line: Callable[[str], None], cwd: Path = REPO_ROOT) -> int:
    """Run `cmd`, calling `on_line` for each combined stdout/stderr line.

    Synchronous and blocking — intended to be called from a worker thread.
    Returns the process exit code.
    """
    process = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=demo_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        on_line(line.rstrip("\n"))
    return process.wait()
