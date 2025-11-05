# Karasu | A Smart Ruff Black Bird [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/) [![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> One-shot formatter enforcer for Python repos. Sets up Ruff, Black, pre-commit hooks, CI workflows, and more—all in a single command.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [What Gets Created](#what-gets-created)
- [Integration with Feza](#integration-with-feza)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Requirements](#requirements)
- [Idempotency](#idempotency)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Complete setup**: Configures formatting, linting, and CI in one go
- **Idempotent**: Safe to run multiple times; only adds missing pieces
- **Auto-formatting**: Formats existing code automatically
- **Virtual environment**: Automatically creates `.venv` and installs dependencies
- **Project initialization**: Bootstrap new Python CLI projects with `--initialize`
- **Feza-compatible**: Creates proper `pyproject.toml` entry points for [Feza](https://github.com/joshuboi77/Feza) release tooling

## Installation

### Prerequisites

- Python 3.11 or higher
- `pip` package manager

### Via Homebrew (Recommended)

```bash
brew tap joshuboi77/karasu
brew install karasu
```

### Via pip

```bash
pip install karasu
```

Or with a specific version:
```bash
pip install karasu>=0.1.0
```

### From source

```bash
git clone https://github.com/joshuboi77/Karasu.git
cd Karasu
pip install -e .
```

### MCP Server (Cursor Integration)

Karasu includes an MCP (Model Context Protocol) server for use in Cursor and other MCP-compatible IDEs. This allows you to use Karasu directly within your IDE via AI agents.

**How it works:**
The MCP server is a Node.js bridge that runs inside Cursor and calls the installed `karasu` executable. When you use `karasu_setup` or `karasu_initialize` tools in Cursor, the MCP server:
1. Validates and converts parameters to CLI arguments
2. Finds the `karasu` command in your PATH
3. Executes the command with those arguments
4. Returns the results back to Cursor

**Important:** Both components are required:
- **Karasu executable** - Must be installed and in your PATH (via Homebrew, pip, etc.)
- **MCP server** - Node.js server that provides the bridge to Cursor

**Prerequisites:**
- Node.js 18+ installed
- Karasu installed and in PATH (see [Installation](#installation) above)
  - Verify with: `which karasu` (macOS/Linux) or `where karasu` (Windows)

**Setup:**

1. Navigate to the MCP directory:
```bash
cd Karasu/mcp
npm install
npm run build
```

2. Add to Cursor configuration (`~/.cursor/mcp.json` on macOS/Linux, `%USERPROFILE%\.cursor\mcp.json` on Windows):
```json
{
  "mcpServers": {
    "karasu": {
      "command": "node",
      "args": ["/absolute/path/to/Karasu/mcp/dist/server.js"],
      "env": {}
    }
  }
}
```

3. Restart Cursor. The `karasu_setup` and `karasu_initialize` tools will be available.

**Windows users:** Run `.\setup.ps1` in the `mcp` directory for automated setup.

For detailed MCP server documentation, see [`mcp/README.md`](mcp/README.md).

## Quick Start

### For Existing Projects

Run Karasu in your Python project directory:

```bash
karasu
```

This will:
1. Create `.venv` and install Ruff, pre-commit (and Black if not using `--ruff-only`)
2. Set up `.editorconfig`, `.pre-commit-config.yaml`, `pyproject.toml`
3. Create/update GitHub Actions CI workflow
4. Add dependencies to `requirements-dev.txt`
5. Format all existing Python files
6. Install pre-commit hooks

### For New Projects

Initialize a new Python CLI project:

```bash
karasu --initialize
```

This will:
1. Detect existing package structure (if any) or create flat structure
2. Create a `main.py` template (placed in package directory if package exists, otherwise at root)
3. Prompt for tool name, description, and version
4. Set up complete `pyproject.toml` with package-aware entry point (Feza-compatible)
5. Configure all formatting infrastructure

**Non-interactive mode:**
```bash
karasu --initialize --name mytool --description "My awesome CLI tool" --version 0.1.0
```

## Usage

### Basic Usage

```bash
# Run in current directory
karasu

# Specify project root
karasu --project-root /path/to/project

# Use Ruff only (no Black)
karasu --ruff-only

# Dry run (see what would change)
karasu --dry-run
```

### Options

```
--project-root PATH     Project root directory (default: .)
--python VERSION        Python version for CI/tools (default: 3.11)
--ruff-only            Skip Black; use Ruff formatter only
--dry-run              Show what would change without making changes
--no-format            Skip formatting existing code files
--no-install-hooks     Skip installing pre-commit hooks
--no-venv              Skip creating .venv; use system tools instead
--initialize, --init, -i  Initialize a new Python project
  --name NAME          Tool name (for --initialize, non-interactive)
  --description DESC   Tool description (for --initialize, non-interactive)
  --version VER        Initial version (for --initialize, non-interactive)
```

### Examples

**Set up formatting for an existing project:**
```bash
cd my-python-project
karasu
```

**Initialize a new CLI tool:**
```bash
mkdir my-tool && cd my-tool
git init
karasu --initialize
# Prompts for name, description, version
```

**Set up with Python 3.12:**
```bash
karasu --python 3.12
```

**Ruff-only setup (faster, simpler):**
```bash
karasu --ruff-only
```

**Non-interactive initialization:**
```bash
karasu --initialize \
  --name mytool \
  --description "My awesome CLI tool" \
  --version 0.2.0
```

## What Gets Created

Karasu creates/updates the following files:

### Configuration Files

- **`.editorconfig`** - Editor settings (LF, 4-space indent, etc.)
- **`.pre-commit-config.yaml`** - Pre-commit hooks (Ruff + optional Black)
- **`pyproject.toml`** - Ruff/Black config and (with `--initialize`) project metadata
- **`.github/workflows/ci.yml`** - GitHub Actions CI workflow
- **`requirements-dev.txt`** - Development dependencies

### With `--initialize`

- **`main.py`** - CLI tool template with argparse
  - Placed in package directory if package structure detected (e.g., `{package}/main.py`)
  - Placed at project root if flat structure
- **`pyproject.toml`** - Includes `[project]` section with package-aware entry point for Feza compatibility

### Virtual Environment

- **`.venv/`** - Created automatically with Ruff, pre-commit (and Black if not `--ruff-only`)

## Integration with [Feza](https://github.com/joshuboi77/Feza)

Karasu creates Feza-compatible entry points that work with both package and flat project structures:

**Package structure** (when a package directory exists):
```toml
[project.scripts]
your-tool = "{package}.main:main"
```

**Flat structure** (when no package directory):
```toml
[project.scripts]
your-tool = "main:main"
```

Karasu automatically detects your project structure and creates the appropriate entry point format. This allows [Feza](https://github.com/joshuboi77/Feza) to:
- Auto-detect Python projects
- Generate `create_python_binaries.sh` with correct imports
- Build and release your tool

**Complete workflow:**
```bash
# 1. Initialize project with Karasu
karasu --initialize --name mytool

# 2. Develop your tool...

# 3. Release with Feza
feza plan --name mytool v1.0.0
feza build --name mytool v1.0.0
feza github --name mytool v1.0.0
feza tap --name mytool --formula Mytool v1.0.0
```

## Configuration

### Ruff Configuration

Karasu sets up Ruff with:
- Line length: 100
- Target Python: 3.11 (configurable with `--python`)
- Lint rules: E, F, I, N, W, UP
- Import sorting with isort
- Double quotes

### Black Configuration (if not `--ruff-only`)

- Line length: 100
- Target Python: 3.11
- Same exclusions as Ruff

### CI Workflow

Runs on push/PR to `main`, `master`, or `develop`:
- Checks formatting with Ruff
- Lints with Ruff
- Optionally checks with Black

## Troubleshooting

### "ruff not found"

Karasu automatically creates `.venv` and installs dependencies. If this fails:
- Ensure Python 3.11+ is available
- Check that `pip` is working
- Use `--no-venv` if you prefer system tools

### "working tree is dirty"

Karasu checks for uncommitted changes before running (in some contexts). Commit or stash changes first:
```bash
git add -A && git commit -m "Your changes"
# or
git stash
```

### Pre-commit hooks not working

Ensure hooks are installed:
```bash
pre-commit install
```

Or let Karasu do it automatically (default behavior).

### MCP Server: "karasu command not found"

If you see this error when using Karasu tools in Cursor:

1. **Verify Karasu is installed:**
   ```bash
   which karasu  # macOS/Linux
   where karasu  # Windows
   ```

2. **Ensure Karasu is in PATH:**
   - Homebrew: `brew install karasu` (should automatically add to PATH)
   - pip: May need to add Python Scripts directory to PATH
   - Verify: `karasu --help` should work in terminal

3. **Restart Cursor** after installing Karasu to ensure PATH is updated

4. **Check MCP server logs** in Cursor for detailed error messages

The MCP server requires the `karasu` executable to be installed and accessible in your PATH. The MCP server itself is just a bridge that calls the executable.

## Requirements

- Python 3.11 or higher
- Git (for pre-commit hooks)
- `pip` (usually comes with Python)

Optional:
- Homebrew (for Homebrew installation)
- GitHub CLI `gh` (for some advanced workflows)

## Idempotency

Karasu is designed to be idempotent:
- Won't overwrite existing configuration
- Only adds missing pieces
- Safe to run multiple times
- Merges new sections into existing files

You can run `karasu` multiple times on the same project without fear of breaking existing configurations.

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report bugs**: Open an issue describing the problem
2. **Suggest features**: Share your ideas for improvements
3. **Submit PRs**: Fork, make changes, and open a pull request

Please ensure:
- Code follows the project's style (run `karasu` on your changes!)
- Tests pass (if applicable)
- Documentation is updated

## License

MIT License - see LICENSE file for details.

---

**Made with ❤️ for Python developers**

