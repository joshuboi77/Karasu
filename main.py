#!/usr/bin/env python3
"""
format_setup.py — one-shot formatter enforcer for Python repos.

Usage:
  python format_setup.py [--project-root .] [--python 3.11] [--ruff-only] [--dry-run] [--no-format] [--no-install-hooks] [--no-venv]

What it does:
  - Creates .venv and installs ruff + pre-commit (+ black) if needed (unless --no-venv)
  - Ensures pyproject.toml has Ruff config (and Black unless --ruff-only)
  - Writes .pre-commit-config.yaml (Ruff fix + Ruff formatter; Black optional)
  - Writes .editorconfig (LF, final newline, 4-space indent)
  - Creates/updates .github/workflows/ci.yml with format/lint checks using '.'
  - Adds ruff + pre-commit (+ black) to requirements-dev.txt
  - Formats existing Python files with ruff (unless --no-format)
  - Installs pre-commit hooks (unless --no-install-hooks)
  - Idempotent: merges or appends only when missing; never clobbers existing content
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import venv
from pathlib import Path

RUFf_REV = "v0.6.9"
BLACK_REV = "24.10.0"

EDITORCONFIG = """root = true

[*]
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4

[*.{py,pyi}]
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false
"""

PRECOMMIT_RUFF = f"""repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: {RUFf_REV}
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
"""

PRECOMMIT_BLACK = f"""  - repo: https://github.com/psf/black
    rev: {BLACK_REV}
    hooks:
      - id: black
"""

PYPROJECT_RUFF_BLOCK = """[tool.ruff]
line-length = 100
target-version = "py311"
exclude = [
    ".git",
    "__pycache__",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "htmlcov",
]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E203", "E501"]

[tool.ruff.lint.isort]
combine-as-imports = true

[tool.ruff.format]
quote-style = "double"
"""

PYPROJECT_BLACK_BLOCK = """[tool.black]
line-length = 100
target-version = ["py311"]
extend-exclude = '''
/(
  \\.eggs
  | \\.git
  | \\.hg
  | \\.mypy_cache
  | \\.tox
  | \\.venv
  | build
  | dist
)/
'''
"""

MINIMAL_PYPROJECT_BUILD = """[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"
"""

CI_TEMPLATE = """name: CI

on:
  push:
    branches: [ main, master, develop ]
  pull_request:
    branches: [ main, master, develop ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '{PYVER}'

    - name: Install dev deps
      run: |
        python -m pip install --upgrade pip
        pip install ruff{BLACK_DEP}

    - name: Format check with Ruff
      run: |
        ruff format --check .

    - name: Lint with Ruff
      run: |
        ruff check .

{BLACK_STEP}
"""

BLACK_DEP_STEP = "\n        pip install black"
BLACK_CHECK_STEP = """    - name: Format check with Black (backup)
      run: |
        black --check .
"""

REQ_DEV_HEADER = "# Development dependencies\n"


def upsert_file(path: Path, content: str, dry: bool) -> bool:
    if path.exists():
        return False
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return True


def ensure_editorconfig(root: Path, dry: bool):
    p = root / ".editorconfig"
    if p.exists():
        return False
    return upsert_file(p, EDITORCONFIG, dry)


def ensure_precommit(root: Path, ruff_only: bool, dry: bool):
    p = root / ".pre-commit-config.yaml"
    if p.exists():
        # append missing blocks if not present
        txt = p.read_text()
        changed = False
        if "ruff-pre-commit" not in txt:
            txt = PRECOMMIT_RUFF + ("\n" + txt if txt else "")
            changed = True
        if not ruff_only and "psf/black" not in txt:
            txt = txt.rstrip() + "\n" + PRECOMMIT_BLACK
            changed = True
        if changed and not dry:
            p.write_text(txt)
        return changed
    # create new
    content = PRECOMMIT_RUFF
    if not ruff_only:
        content += PRECOMMIT_BLACK
    return upsert_file(p, content, dry)


def ensure_pyproject(root: Path, ruff_only: bool, pyver: str, dry: bool):
    p = root / "pyproject.toml"
    if p.exists():
        txt = p.read_text()
        changed = False
        # inject Ruff block if missing
        if "[tool.ruff]" not in txt:
            txt = (
                txt.rstrip()
                + ("\n\n" if not txt.endswith("\n") else "\n")
                + PYPROJECT_RUFF_BLOCK.replace('"py311"', f'"py{pyver.replace(".", "")}"')
            )
            changed = True
        # inject Black block if chosen
        if not ruff_only and "[tool.black]" not in txt:
            txt = (
                txt.rstrip()
                + ("\n\n" if not txt.endswith("\n") else "\n")
                + PYPROJECT_BLACK_BLOCK.replace('"py311"', f'"py{pyver.replace(".", "")}"')
            )
            changed = True
        if changed and not dry:
            p.write_text(txt)
        return changed
    # create minimal + ruff (+ black)
    body = (
        MINIMAL_PYPROJECT_BUILD
        + "\n\n"
        + PYPROJECT_RUFF_BLOCK.replace('"py311"', f'"py{pyver.replace(".", "")}"')
    )
    if not ruff_only:
        body += "\n\n" + PYPROJECT_BLACK_BLOCK.replace('"py311"', f'"py{pyver.replace(".", "")}"')
    return upsert_file(p, body, dry)


def ensure_ci(root: Path, ruff_only: bool, pyver: str, dry: bool):
    p = root / ".github" / "workflows" / "ci.yml"
    black_dep = "" if ruff_only else BLACK_DEP_STEP
    black_step = "" if ruff_only else BLACK_CHECK_STEP
    if p.exists():
        txt = p.read_text()
        changed = False
        if "ruff format --check" not in txt or "ruff check" not in txt:
            # naive insertion: append our job
            txt = (
                txt.rstrip()
                + "\n\n"
                + CI_TEMPLATE.format(PYVER=pyver, BLACK_DEP=black_dep, BLACK_STEP=black_step)
            )
            changed = True
        elif (not ruff_only) and "black --check" not in txt:
            # add Black step
            # place after Ruff steps
            if not txt.endswith("\n"):
                txt += "\n"
            txt += "\n" + BLACK_CHECK_STEP
            changed = True
        if changed and not dry:
            p.write_text(txt)
        return changed
    # create fresh CI
    content = CI_TEMPLATE.format(PYVER=pyver, BLACK_DEP=black_dep, BLACK_STEP=black_step)
    return upsert_file(p, content, dry)


def ensure_requirements_dev(root: Path, ruff_only: bool, dry: bool):
    p = root / "requirements-dev.txt"
    want = ["ruff>=0.6.9", "pre-commit>=3.0.0"] + ([] if ruff_only else ["black>=24.10.0"])
    if p.exists():
        txt = p.read_text()
        missing = [w for w in want if re.search(rf"(?m)^{re.escape(w.split('>')[0])}", txt) is None]
        if not missing:
            return False
        if not dry:
            if not txt.strip().startswith("#"):
                txt = REQ_DEV_HEADER + txt
            txt = txt.rstrip() + "\n" + "\n".join(missing) + "\n"
            p.write_text(txt)
        return True
    content = REQ_DEV_HEADER + "\n".join(want) + "\n"
    return upsert_file(p, content, dry)


def ensure_venv_and_deps(root: Path, ruff_only: bool, dry: bool) -> Path | None:
    """Create .venv if needed and install dependencies. Returns path to venv's Python or None."""
    venv_path = root / ".venv"
    venv_python = venv_path / "bin" / "python"
    if sys.platform == "win32":
        venv_python = venv_path / "Scripts" / "python.exe"

    if venv_path.exists():
        print("Using existing .venv")
        return venv_python

    if dry:
        print("Would create .venv and install dependencies...")
        return venv_python

    print("Creating .venv...")
    try:
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_path)
    except Exception as e:
        print(f"Warning: Failed to create .venv: {e}", file=sys.stderr)
        return None

    if not venv_python.exists():
        print(f"Warning: .venv created but Python not found at {venv_python}", file=sys.stderr)
        return None

    print("Installing dependencies into .venv...")
    deps = ["ruff>=0.6.9", "pre-commit>=3.0.0"]
    if not ruff_only:
        deps.append("black>=24.10.0")

    # Install dependencies
    result = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet"] + deps,
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        print(f"Warning: Failed to install dependencies: {result.stderr}", file=sys.stderr)
        return None

    print(f"Installed: {', '.join(deps)}")
    return venv_python


def get_tool_command(root: Path, venv_python: Path | None, tool: str) -> list[str]:
    """Get command to run a tool, using venv if available, otherwise system PATH."""
    if venv_python:
        # Use venv's tool
        if sys.platform == "win32":
            tool_path = venv_python.parent / f"{tool}.exe"
        else:
            tool_path = venv_python.parent / tool
        if tool_path.exists():
            return [str(tool_path)]
        # Fallback to python -m
        return [str(venv_python), "-m", tool]
    # Use system PATH
    return [tool]


def format_code(root: Path, ruff_only: bool, dry: bool, venv_python: Path | None = None) -> bool:
    """Format existing Python files with ruff (and optionally black)."""
    if dry:
        print("Would format code with ruff...")
        return True

    # Try to use ruff
    ruff_cmd = get_tool_command(root, venv_python, "ruff")
    try:
        result = subprocess.run([*ruff_cmd, "--version"], capture_output=True, text=True, cwd=root)
        if result.returncode != 0:
            print("Warning: ruff not found. Install with: pip install ruff")
            return False
    except FileNotFoundError:
        print("Warning: ruff not found. Install with: pip install ruff")
        return False

    formatted = False

    # Format with ruff
    print("Formatting code with ruff...")
    result = subprocess.run([*ruff_cmd, "format", "."], capture_output=True, text=True, cwd=root)
    if result.returncode == 0:
        if result.stdout.strip():
            print(result.stdout.strip())
            formatted = True
    else:
        print(f"Warning: ruff format failed: {result.stderr}", file=sys.stderr)

    # Fix linting issues with ruff
    print("Fixing linting issues with ruff...")
    result = subprocess.run(
        [*ruff_cmd, "check", "--fix", "."], capture_output=True, text=True, cwd=root
    )
    # Ruff returns exit code 1 when it fixes issues (expected), 0 when clean, 2 on error
    if result.returncode in (0, 1):
        if result.stdout.strip():
            print(result.stdout.strip())
        formatted = True
    else:
        # Exit code 2 indicates an actual error
        print(f"Warning: ruff check had errors: {result.stderr}", file=sys.stderr)

    # Optionally format with black
    if not ruff_only:
        black_cmd = get_tool_command(root, venv_python, "black")
        try:
            result = subprocess.run(
                [*black_cmd, "--version"], capture_output=True, text=True, cwd=root
            )
            if result.returncode == 0:
                print("Formatting code with black...")
                result = subprocess.run([*black_cmd, "."], capture_output=True, text=True, cwd=root)
                if result.returncode == 0:
                    if result.stdout.strip():
                        print(result.stdout.strip())
                        formatted = True
        except FileNotFoundError:
            print("Warning: black not found. Skipping black formatting.")

    return formatted


def install_precommit_hooks(root: Path, dry: bool, venv_python: Path | None = None) -> bool:
    """Install pre-commit hooks."""
    if dry:
        print("Would install pre-commit hooks...")
        return True

    # Check if pre-commit is available
    precommit_cmd = get_tool_command(root, venv_python, "pre-commit")
    try:
        result = subprocess.run(
            [*precommit_cmd, "--version"], capture_output=True, text=True, cwd=root
        )
        if result.returncode != 0:
            print("Warning: pre-commit not found. Install with: pip install pre-commit")
            return False
    except FileNotFoundError:
        print("Warning: pre-commit not found. Install with: pip install pre-commit")
        return False

    # Check if .pre-commit-config.yaml exists
    config = root / ".pre-commit-config.yaml"
    if not config.exists():
        print("Warning: .pre-commit-config.yaml not found. Skipping hook installation.")
        return False

    print("Installing pre-commit hooks...")
    result = subprocess.run([*precommit_cmd, "install"], capture_output=True, text=True, cwd=root)
    if result.returncode == 0:
        print("Pre-commit hooks installed successfully.")
        return True
    else:
        print(f"Warning: pre-commit install failed: {result.stderr}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--python", default="3.11", help="Python version for CI/tools (e.g., 3.11)")
    ap.add_argument("--ruff-only", action="store_true", help="Skip Black; use Ruff formatter only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--no-format",
        action="store_true",
        help="Skip formatting existing code files",
    )
    ap.add_argument(
        "--no-install-hooks",
        action="store_true",
        help="Skip installing pre-commit hooks",
    )
    ap.add_argument(
        "--no-venv",
        action="store_true",
        help="Skip creating .venv; use system tools instead",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()

    # Create venv and install dependencies (unless --no-venv)
    venv_python = None
    if not args.no_venv and not args.dry_run:
        venv_python = ensure_venv_and_deps(root, args.ruff_only, args.dry_run)

    actions = []
    actions.append(("editorconfig", ensure_editorconfig(root, args.dry_run)))
    actions.append(("pre-commit", ensure_precommit(root, args.ruff_only, args.dry_run)))
    actions.append(("pyproject", ensure_pyproject(root, args.ruff_only, args.python, args.dry_run)))
    actions.append(("ci", ensure_ci(root, args.ruff_only, args.python, args.dry_run)))
    actions.append(
        ("requirements-dev", ensure_requirements_dev(root, args.ruff_only, args.dry_run))
    )

    created_or_changed = [name for name, changed in actions if changed]
    if created_or_changed:
        print("Updated:", ", ".join(created_or_changed))
    else:
        print("No changes; everything already in place.")

    # Format existing code (unless --no-format)
    if not args.no_format and not args.dry_run:
        format_code(root, args.ruff_only, args.dry_run, venv_python)

    # Install pre-commit hooks (unless --no-install-hooks)
    if not args.no_install_hooks and not args.dry_run:
        install_precommit_hooks(root, args.dry_run, venv_python)

    if args.dry_run:
        print("\nNext steps (run without --dry-run to execute):")
        print("  pip install -r requirements-dev.txt || pip install ruff pre-commit black")
        if not args.no_install_hooks:
            print("  pre-commit install")
        if not args.no_format:
            print("  ruff format . && ruff check --fix .")
            if not args.ruff_only:
                print("  black .")
        print("  git add -A && git commit -m 'style: enforce Ruff/Black formatting'")


if __name__ == "__main__":
    main()
