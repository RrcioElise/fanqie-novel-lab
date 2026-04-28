param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "未找到 .venv。请先运行：.\scripts\setup.ps1"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js LTS，然后重新打开 PowerShell。"
}

$env:PYTHONUTF8 = "1"
$env:FANQIE_LAB_PORT = "$Port"

Set-Location (Join-Path $Root "electron-client")

if (-not (Test-Path "node_modules")) {
    if (Test-Path "package-lock.json") {
        npm ci --cache (Join-Path $Root ".npm-cache")
    }
    else {
        npm install --cache (Join-Path $Root ".npm-cache")
    }
}

npm start --cache (Join-Path $Root ".npm-cache")
