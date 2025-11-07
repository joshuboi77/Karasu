#!/usr/bin/env node
/**
 * Karasu MCP Server
 * 
 * Model Context Protocol server that exposes Karasu CLI commands as tools
 * for use in Cursor and other MCP-compatible IDEs.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn, execSync } from "node:child_process";
import { z } from "zod";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const server = new Server(
  {
    name: "karasu-mcp",
    version: "0.3.3",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * MCP TOOLS FOR AI AGENTS:
 * 
 * When user asks to "format this project", "set up ruff/black", "add formatting",
 * or similar formatting-related tasks, use karasu_setup.
 * 
 * When user asks to "create new Python project", "initialize CLI tool", "bootstrap project",
 * or wants to start a new project, use karasu_initialize.
 * 
 * These tools are PREFERRED over running 'karasu' CLI commands directly.
 */

/**
 * Detect project root directory by looking for git root or project indicators.
 * Falls back to current working directory if nothing found.
 */
function detectProjectRoot(): string {
  const startDir = process.cwd();
  
  // Try 1: Git root (most reliable for projects in git repos)
  try {
    const gitRoot = execSync("git rev-parse --show-toplevel", {
      cwd: startDir,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
    if (gitRoot && existsSync(gitRoot)) {
      return gitRoot;
    }
  } catch {
    // Git command failed, continue to next method
  }
  
  // Try 2: Walk up directory tree looking for project indicators
  let currentDir = path.resolve(startDir);
  const root = path.parse(currentDir).root;
  
  while (currentDir !== root) {
    // Check for common project files
    const indicators = [
      "pyproject.toml",
      "package.json",
      "Cargo.toml",
      "go.mod",
      ".git",
      "Makefile",
    ];
    
    for (const indicator of indicators) {
      if (existsSync(path.join(currentDir, indicator))) {
        return currentDir;
      }
    }
    
    // Move up one directory
    currentDir = path.dirname(currentDir);
  }
  
  // Fallback: return current working directory
  return startDir;
}

/**
 * Resolve command path, checking PATH and common Homebrew locations
 */
function resolveCommand(cmd: string): string {
  // Try PATH first - use 'which' on Unix, 'where' on Windows
  const whichCmd = process.platform === "win32" ? "where" : "which";
  try {
    const result = execSync(`${whichCmd} ${cmd}`, {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    const whichResult = result.trim().split("\n")[0]; // Take first result if multiple
    if (whichResult && existsSync(whichResult)) {
      return whichResult;
    }
  } catch {
    // which/where failed, continue to Homebrew checks
  }

  // Try common Homebrew locations (mainly for macOS/Linux)
  const homebrewPaths = [
    "/opt/homebrew/bin", // Apple Silicon
    "/usr/local/bin",    // Intel Mac / Linux with Homebrew
    process.env.HOMEBREW_PREFIX ? `${process.env.HOMEBREW_PREFIX}/bin` : null,
  ].filter(Boolean) as string[];

  for (const basePath of homebrewPaths) {
    const fullPath = path.join(basePath, cmd);
    if (existsSync(fullPath)) {
      return fullPath;
    }
  }

  // Fallback: return original command (spawn will handle the error)
  return cmd;
}

/**
 * Run Karasu command and return result
 */
function runKarasu(
  args: string[],
  cwd?: string
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const cmdPath = resolveCommand("karasu");
    const workingDir = cwd || detectProjectRoot();
    const childProcess = spawn(cmdPath, args, {
      cwd: workingDir,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      shell: true,
    });

    let stdout = "";
    let stderr = "";

    childProcess.stdout?.on("data", (data: Buffer) => {
      stdout += data.toString();
    });

    childProcess.stderr?.on("data", (data: Buffer) => {
      stderr += data.toString();
    });

    childProcess.on("close", (code: number | null) => {
      resolve({
        code: code ?? 1,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
      });
    });

    childProcess.on("error", (error: Error) => {
      if (error.message.includes("ENOENT")) {
        resolve({
          code: 1,
          stdout: "",
          stderr: `karasu command not found. Install with: brew install karasu\nOr pip install karasu\nOr ensure karasu is on your PATH.\nOriginal error: ${error.message}`,
        });
      } else {
        resolve({
          code: 1,
          stdout: "",
          stderr: `Failed to spawn karasu: ${error.message}`,
        });
      }
    });
  });
}

// Tool registry
const tools: Array<{
  name: string;
  description: string;
  schema: z.ZodTypeAny;
  toArgs: (input: any) => string[];
}> = [];

/**
 * Register a tool with the MCP server
 */
function registerTool(
  name: string,
  description: string,
  schema: z.ZodTypeAny,
  toArgs: (input: any) => string[]
) {
  tools.push({ name, description, schema, toArgs });
}

// Tool schemas using Zod
const SetupSchema = z.object({
  projectRoot: z.string().optional().describe("Project root directory. Auto-detected from git root or current directory if not provided. Usually omit to use auto-detection."),
  python: z.string().optional().describe("Python version for CI/tools (default: 3.11). Use '3.12' or '3.13' for newer projects. Format: '3.11', '3.12', etc."),
  ruffOnly: z.boolean().optional().describe("Skip Black; use Ruff formatter only. Default: false (uses both Ruff and Black). Set to true for faster, simpler setup with just Ruff."),
  dryRun: z.boolean().optional().describe("Show what would change without making changes. Default: false. Set to true to preview changes before applying."),
  noFormat: z.boolean().optional().describe("Skip formatting existing code files. Default: false (formats code automatically). Set to true only if you want to skip formatting."),
  noInstallHooks: z.boolean().optional().describe("Skip installing pre-commit hooks. Default: false (installs hooks automatically). Set to true only if you want to skip hook installation."),
  noVenv: z.boolean().optional().describe("Skip creating .venv; use system tools instead. Default: false (creates .venv automatically). Set to true only if you want to use system-wide tools instead of project venv."),
});

const InitializeSchema = z.object({
  name: z.string().optional().describe("Tool name (required for non-interactive mode). Will prompt interactively if not provided. Use lowercase with hyphens (e.g., 'my-tool')."),
  description: z.string().optional().describe("Tool description (required for non-interactive mode). Will prompt interactively if not provided. Short description of what the tool does."),
  version: z.string().optional().describe("Initial version (default: 0.1.0). Use semantic versioning format (e.g., '0.1.0', '1.0.0')."),
  projectRoot: z.string().optional().describe("Project root directory. Auto-detected from git root or current directory if not provided. Usually omit to use auto-detection."),
  python: z.string().optional().describe("Python version for CI/tools (default: 3.11). Use '3.12' or '3.13' for newer projects. Format: '3.11', '3.12', etc."),
  ruffOnly: z.boolean().optional().describe("Skip Black; use Ruff formatter only. Default: false (uses both Ruff and Black). Set to true for faster, simpler setup with just Ruff."),
  dryRun: z.boolean().optional().describe("Show what would change without making changes. Default: false. Set to true to preview changes before applying."),
  noFormat: z.boolean().optional().describe("Skip formatting existing code files. Default: false (formats code automatically). Set to true only if you want to skip formatting."),
  noInstallHooks: z.boolean().optional().describe("Skip installing pre-commit hooks. Default: false (installs hooks automatically). Set to true only if you want to skip hook installation."),
  noVenv: z.boolean().optional().describe("Skip creating .venv; use system tools instead. Default: false (creates .venv automatically). Set to true only if you want to use system-wide tools instead of project venv."),
});

// Register all tools
registerTool(
  "karasu_setup",
  "[MCP TOOL - USE THIS] Set up formatting infrastructure for an existing Python project. Use when user asks to 'format this project', 'set up ruff/black', 'add formatting', 'enforce code style', or 'configure linting'. Creates .venv, configures Ruff/Black, pre-commit hooks, CI workflows, and formats existing code. Preferred over 'karasu' CLI command for AI agents.",
  SetupSchema,
  (input) => {
    const args: string[] = [];
    if (input.projectRoot) args.push("--project-root", input.projectRoot);
    if (input.python) args.push("--python", input.python);
    if (input.ruffOnly) args.push("--ruff-only");
    if (input.dryRun) args.push("--dry-run");
    if (input.noFormat) args.push("--no-format");
    if (input.noInstallHooks) args.push("--no-install-hooks");
    if (input.noVenv) args.push("--no-venv");
    return args;
  }
);

registerTool(
  "karasu_initialize",
  "[MCP TOOL - USE THIS] Initialize a new Python CLI project with formatting infrastructure. Use when user asks to 'create new Python project', 'initialize CLI tool', 'bootstrap project', 'start new tool', or 'create Python CLI'. Creates main.py template, pyproject.toml with entry points (Feza-compatible), and all formatting config. Preferred over 'karasu --initialize' CLI command for AI agents.",
  InitializeSchema,
  (input) => {
    const args = ["--initialize"];
    if (input.name) args.push("--name", input.name);
    if (input.description) args.push("--description", input.description);
    if (input.version) args.push("--version", input.version);
    if (input.projectRoot) args.push("--project-root", input.projectRoot);
    if (input.python) args.push("--python", input.python);
    if (input.ruffOnly) args.push("--ruff-only");
    if (input.dryRun) args.push("--dry-run");
    if (input.noFormat) args.push("--no-format");
    if (input.noInstallHooks) args.push("--no-install-hooks");
    if (input.noVenv) args.push("--no-venv");
    return args;
  }
);

// Helper to convert Zod schema to JSON Schema
function zodToJsonSchema(zodSchema: z.ZodTypeAny): any {
  // Basic implementation that handles ZodObject schemas
  const shape = zodSchema._def;
  if (shape.typeName === "ZodObject") {
    const jsonSchema: any = {
      type: "object",
      properties: {},
      required: [],
    };
    const objShape = shape.shape();
    for (const [key, value] of Object.entries(objShape)) {
      const field = value as z.ZodTypeAny;
      let fieldDef = field._def;
      let isOptional = false;
      
      // Handle ZodOptional
      if (fieldDef.typeName === "ZodOptional") {
        isOptional = true;
        fieldDef = fieldDef.innerType._def;
      }
      
      // Handle ZodDefault (which wraps ZodOptional sometimes)
      if (fieldDef.typeName === "ZodDefault") {
        isOptional = true;
        fieldDef = fieldDef.innerType._def;
        // Handle nested ZodOptional
        if (fieldDef.typeName === "ZodOptional") {
          fieldDef = fieldDef.innerType._def;
        }
      }
      
      // Extract description
      const description = fieldDef.description || (field as any).description;
      
      if (fieldDef.typeName === "ZodString") {
        jsonSchema.properties[key] = { type: "string", description };
      } else if (fieldDef.typeName === "ZodNumber") {
        jsonSchema.properties[key] = { type: "number", description };
      } else if (fieldDef.typeName === "ZodBoolean") {
        jsonSchema.properties[key] = { type: "boolean", description };
      } else {
        jsonSchema.properties[key] = { description };
      }
      
      if (!isOptional) {
        jsonSchema.required.push(key);
      }
    }
    return jsonSchema;
  }
  return { type: "object" };
}

// Register request handlers
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: tools.map((tool) => {
      const schema = zodToJsonSchema(tool.schema);
      return {
        name: tool.name,
        description: tool.description,
        inputSchema: schema,
      };
    }),
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  const tool = tools.find((t) => t.name === name);
  if (!tool) {
    throw new McpError(
      ErrorCode.MethodNotFound,
      `Tool not found: ${name}`
    );
  }

  try {
    // Validate input with Zod schema
    const validatedInput = tool.schema.parse(args || {});
    
    // Convert to Karasu CLI args
    const karasuArgs = tool.toArgs(validatedInput);
    const cwd = validatedInput.projectRoot;

    // Execute Karasu command
    const result = await runKarasu(karasuArgs, cwd);

    if (result.code !== 0) {
      return {
        content: [
          {
            type: "text",
            text: `Error: ${result.stderr || "Unknown error"}\n${result.stdout}`,
          },
        ],
        isError: true,
      };
    }

    return {
      content: [
        {
          type: "text",
          text: result.stdout || "Success",
        },
      ],
    };
  } catch (error: any) {
    if (error instanceof z.ZodError) {
      throw new McpError(
        ErrorCode.InvalidParams,
        `Invalid parameters: ${error.errors.map((e) => e.message).join(", ")}`
      );
    }
    throw new McpError(
      ErrorCode.InternalError,
      `Tool execution failed: ${error.message}`
    );
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Karasu MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});

