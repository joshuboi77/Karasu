# Karasu MCP Server Setup Script for Windows
# This script installs dependencies and builds the MCP server

Write-Host "Karasu MCP Server Setup" -ForegroundColor Cyan
Write-Host "=======================" -ForegroundColor Cyan
Write-Host ""

# Check for Node.js
Write-Host "Checking for Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "Found Node.js: $nodeVersion" -ForegroundColor Green
    
    # Check if version is >= 18
    $majorVersion = [int]($nodeVersion -replace 'v(\d+)\..*', '$1')
    if ($majorVersion -lt 18) {
        Write-Host "ERROR: Node.js 18+ is required. Found version $nodeVersion" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Node.js 18+ from: https://nodejs.org/" -ForegroundColor Yellow
    Write-Host "After installing Node.js, run this script again." -ForegroundColor Yellow
    exit 1
}

# Check for npm
Write-Host "Checking for npm..." -ForegroundColor Yellow
try {
    $npmVersion = npm --version
    Write-Host "Found npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: npm is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Build the TypeScript code
Write-Host ""
Write-Host "Building TypeScript code..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build TypeScript code" -ForegroundColor Red
    exit 1
}

# Verify build output
$distPath = Join-Path $scriptDir "dist\server.js"
if (Test-Path $distPath) {
    Write-Host ""
    Write-Host "Build successful! Server available at:" -ForegroundColor Green
    Write-Host $distPath -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Build output not found at $distPath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Add Karasu MCP server to your Cursor configuration:" -ForegroundColor White
Write-Host "   Edit or create: %USERPROFILE%\.cursor\mcp.json" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Add this configuration:" -ForegroundColor White
Write-Host '   {'
Write-Host '     "mcpServers": {'
Write-Host '       "karasu": {'
Write-Host '         "command": "node",'
Write-Host "         \"args\": [\"$distPath\"],"
Write-Host '         "env": {}'
Write-Host '       }'
Write-Host '     }'
Write-Host '   }'
Write-Host ""
Write-Host "3. Restart Cursor to load the MCP server" -ForegroundColor White
Write-Host ""

