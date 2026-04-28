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

$env:PYTHONUTF8 = "1"
& $VenvPython -m streamlit run "src\fanqie_novel_lab\app.py" `
    --server.address "127.0.0.1" `
    --server.port $Port `
    --browser.gatherUsageStats "false"
