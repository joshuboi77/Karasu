#!/usr/bin/env python3
"""
format_setup.py — one-shot formatter enforcer for Python repos.

Usage:
  python format_setup.py [--project-root .] [--python 3.11] [--ruff-only] [--dry-run]

What it does:
  - Ensures pyproject.toml has Ruff config (and Black unless --ruff-only)
  - Writes .pre-commit-config.yaml (Ruff fix + Ruff formatter; Black optional)
  - Writes .editorconfig (LF, final newline, 4-space indent)
  - Creates/updates .github/workflows/ci.yml with format/lint checks using '.'
  - Adds ruff + pre-commit (+ black) to requirements-dev.txt
  - Idempotent: merges or appends only when missing; never clobbers existing content
"""

from __future__ import annotations

import argparse
import re
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--python", default="3.11", help="Python version for CI/tools (e.g., 3.11)")
    ap.add_argument("--ruff-only", action="store_true", help="Skip Black; use Ruff formatter only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()

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
    if not args.dry_run:
        print("\nNext steps:")
        print("  pip install -r requirements-dev.txt || pip install ruff pre-commit black")
        print("  pre-commit install")
        print("  ruff format . && ruff check --fix .")
        if not args.ruff_only:
            print("  black .")
        print("  git add -A && git commit -m 'style: enforce Ruff/Black formatting'")


if __name__ == "__main__":
    main()
