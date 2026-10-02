#!/usr/bin/env bash
# Shared launcher logic for the scripts/demo Textual TUIs (tui-setup, tui-demo).
# Mirrors the venv-bootstrap pattern used by ./tui-cci at the repo root, scoped
# to its own venv (.harness/demo-tui-venv) so it doesn't interfere with the
# build-harness TUI's own venv/deps.
#
# Usage: source this file, then call `_demo_tui_launch <python-module> "$@"`.

_demo_tui_launch() {
  local module="$1"
  shift || true

  local root_dir venv_dir venv_python req_file req_marker
  # BASH_SOURCE[0] here resolves to this file's own path (scripts/demo/tui/_bootstrap.sh),
  # not the caller's — three levels up (tui -> demo -> scripts -> repo root), not two.
  root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  venv_dir="$root_dir/.harness/demo-tui-venv"
  venv_python="$venv_dir/bin/python"
  req_file="$root_dir/scripts/demo/tui/requirements.txt"
  req_marker="$venv_dir/.requirements.sha256"

  # VS Code/Cursor can fail shell-environment resolution when SHELL is unset.
  if [[ -z "${SHELL:-}" || ! -x "${SHELL:-}" ]]; then
    if [[ -x "/bin/zsh" ]]; then
      export SHELL="/bin/zsh"
    elif [[ -x "/bin/bash" ]]; then
      export SHELL="/bin/bash"
    fi
  fi

  # Textual requires an interactive TTY; avoid blank output in non-interactive
  # contexts. DEMO_TUI_SKIP_TTY_CHECK=1 exists for automated launcher tests.
  if [[ "${DEMO_TUI_SKIP_TTY_CHECK:-0}" != "1" ]]; then
    if [[ ! -t 0 || ! -t 1 || ! -t 2 ]]; then
      echo "This TUI requires an interactive terminal."
      echo "Run it from a local terminal or VS Code integrated terminal."
      return 1
    fi
  fi

  if [[ -t 1 && ( -z "${TERM:-}" || "${TERM:-}" == "dumb" ) ]]; then
    export TERM="xterm-256color"
  fi

  trap 'stty sane 2>/dev/null || true' EXIT INT TERM

  local req_hash=""
  if [[ -f "$req_file" ]]; then
    if command -v sha256sum >/dev/null 2>&1; then
      req_hash="$(sha256sum "$req_file" 2>/dev/null | awk '{print $1}')" || true
    elif command -v shasum >/dev/null 2>&1; then
      req_hash="$(shasum -a 256 "$req_file" 2>/dev/null | awk '{print $1}')" || true
    fi
  else
    echo "demo TUI: requirements file not found at $req_file" >&2
    return 1
  fi

  if [[ ! -x "$venv_python" ]]; then
    local bootstrap_python=""
    for candidate in python3 python; do
      if command -v "$candidate" >/dev/null 2>&1; then
        bootstrap_python="$candidate"
        break
      fi
    done
    if [[ -z "$bootstrap_python" ]] \
      || ! "$bootstrap_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      echo "demo TUI requires Python 3.11+ on PATH (python3 or python)."
      return 1
    fi
    echo "Creating scoped TUI virtual environment at $venv_dir..."
    mkdir -p "$root_dir/.harness"
    "$bootstrap_python" -m venv "$venv_dir"
  fi

  local deps_ok=1
  if [[ -n "$req_hash" && -f "$req_marker" && "$(cat "$req_marker" 2>/dev/null)" == "$req_hash" ]]; then
    "$venv_python" -c "import textual" >/dev/null 2>&1 && deps_ok=0
  fi
  if [[ "$deps_ok" -ne 0 ]]; then
    echo "Installing TUI dependencies..."
    "$venv_python" -m pip install -q -r "$req_file"
    if [[ -n "$req_hash" ]]; then
      printf '%s\n' "$req_hash" >"$req_marker"
    fi
  fi

  cd "$root_dir"
  set +e
  "$venv_python" -m "$module" "$@"
  local exit_code=$?
  set -e
  if [[ $exit_code -ne 0 ]]; then
    echo "[$module] exited with code $exit_code"
  fi
  return $exit_code
}
