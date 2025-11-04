# Karasu MCP Server

Model Context Protocol (MCP) server that exposes Karasu CLI commands as tools for use in Cursor and other MCP-compatible IDEs.

## Overview

This MCP server allows you to use Karasu directly within Cursor, making Python project formatting setup accessible to AI agents and automation. The server exposes two main tools:

- **karasu_setup** - Set up formatting infrastructure for existing Python projects
- **karasu_initialize** - Initialize a new Python CLI project with formatting infrastructure

## Installation

### Prerequisites

- Node.js 18+ 
- Karasu installed (Homebrew: `brew install karasu` or `pip install karasu`)
- Karasu must be in your PATH

### Setup

1. Install dependencies:
```bash
cd mcp
npm install
```

2. Build the TypeScript code:
```bash
npm run build
```

3. The server will be available at `dist/server.js`

### Windows Setup

Run the PowerShell setup script:
```powershell
.\setup.ps1
```

This will:
- Check for Node.js 18+
- Install dependencies
- Build the TypeScript code
- Provide instructions for Cursor configuration

## Cursor Configuration

Add Karasu MCP server to your Cursor configuration:

### macOS/Linux

Edit or create `~/.cursor/mcp.json`:

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

### Windows

Edit or create `%USERPROFILE%\.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "karasu": {
      "command": "node",
      "args": ["C:\\full\\path\\to\\Karasu\\mcp\\dist\\server.js"],
      "env": {}
    }
  }
}
```

## Usage in Cursor

After configuring and restarting Cursor:

1. Open Cursor's tools panel
2. You should see `karasu_setup` and `karasu_initialize` available
3. Use them in chat or agent mode to automate Python project formatting setup

### Example Agent Workflow

**Set up formatting for an existing project:**
```
karasu_setup(projectRoot="./my-project", python="3.11", ruffOnly=false)
```

**Initialize a new Python CLI project:**
```
karasu_initialize(
  name="my-tool",
  description="My awesome CLI tool",
  version="0.1.0",
  python="3.11",
  ruffOnly=false
)
```

## Development

### Running in Development Mode

```bash
npm run dev
```

This uses `tsx` to run TypeScript directly without building.

### Building

```bash
npm run build
```

### Testing Locally

You can test the server manually using the MCP inspector or by connecting from Cursor.

## Tool Reference

### karasu_setup

Sets up formatting infrastructure for an existing Python project.

**Parameters:**
- `projectRoot` (string, optional) - Project root directory (default: auto-detect)
- `python` (string, optional) - Python version for CI/tools (default: 3.11)
- `ruffOnly` (boolean, optional) - Skip Black; use Ruff formatter only
- `dryRun` (boolean, optional) - Show what would change without making changes
- `noFormat` (boolean, optional) - Skip formatting existing code files
- `noInstallHooks` (boolean, optional) - Skip installing pre-commit hooks
- `noVenv` (boolean, optional) - Skip creating .venv; use system tools instead

**What it does:**
- Creates `.venv` and installs Ruff, pre-commit (and Black if not `--ruff-only`)
- Sets up `.editorconfig`, `.pre-commit-config.yaml`, `pyproject.toml`
- Creates/updates `.github/workflows/ci.yml` with format/lint checks
- Adds dependencies to `requirements-dev.txt`
- Formats existing Python files (unless `--no-format`)
- Installs pre-commit hooks (unless `--no-install-hooks`)

### karasu_initialize

Initializes a new Python CLI project with formatting infrastructure.

**Parameters:**
- `name` (string, optional) - Tool name (for non-interactive mode)
- `description` (string, optional) - Tool description (for non-interactive mode)
- `version` (string, optional) - Initial version (default: 0.1.0)
- `projectRoot` (string, optional) - Project root directory (default: auto-detect)
- `python` (string, optional) - Python version for CI/tools (default: 3.11)
- `ruffOnly` (boolean, optional) - Skip Black; use Ruff formatter only
- `dryRun` (boolean, optional) - Show what would change without making changes
- `noFormat` (boolean, optional) - Skip formatting existing code files
- `noInstallHooks` (boolean, optional) - Skip installing pre-commit hooks
- `noVenv` (boolean, optional) - Skip creating .venv; use system tools instead

**What it does:**
- Creates `main.py` template with argparse
- Sets up `pyproject.toml` with `[project]` section and entry point
- Configures all formatting infrastructure (same as `karasu_setup`)
- Prompts for name, description, and version if not provided

## Troubleshooting

### "karasu: command not found"

Ensure Karasu is installed and in your PATH:
- Homebrew: `brew install karasu`
- pip: `pip install karasu`
- Check: `which karasu` (macOS/Linux) or `where karasu` (Windows)

### MCP Server Not Appearing

1. Check that the path in `mcp.json` is absolute and correct
2. Restart Cursor after changing `mcp.json`
3. Check Cursor's MCP server logs for errors
4. Verify Node.js version: `node --version` (needs 18+)
5. Verify the build was successful: check that `dist/server.js` exists

### Build Errors

If you encounter TypeScript build errors:
1. Ensure all dependencies are installed: `npm install`
2. Check Node.js version: `node --version` (needs 18+)
3. Try deleting `node_modules` and `dist` and running `npm install` again

## License

MIT (same as Karasu)

