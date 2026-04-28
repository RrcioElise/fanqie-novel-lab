param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Get-PythonLauncher {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Command = "py"; Args = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Command = "python"; Args = @() }
    }
    throw "未找到 Python。请先安装 Python 3.10+，并勾选 Add python.exe to PATH。"
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if ($Force -and (Test-Path ".venv")) {
    Remove-Item ".venv" -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    $PythonLauncher = Get-PythonLauncher
    $PythonCommand = $PythonLauncher["Command"]
    $PythonArgs = $PythonLauncher["Args"]
    & $PythonCommand @PythonArgs -m venv .venv
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e .

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已创建 .env；你可以稍后在客户端“项目设置 → 模型”里配置模型。"
}

& $VenvPython -m fanqie_novel_lab.cli init-db

Write-Host ""
Write-Host "Windows 初始化完成。"
Write-Host "启动 Web UI：      .\scripts\run_app.ps1"
Write-Host "启动桌面客户端：   .\scripts\run_electron.ps1"
