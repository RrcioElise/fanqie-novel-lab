# Windows Guide

本项目支持 Windows 10/11。推荐使用 PowerShell 启动。

## 前置依赖

1. Python 3.10+
   - 安装时勾选 **Add python.exe to PATH**。
   - 安装后重新打开 PowerShell。
2. Node.js LTS
   - 仅桌面客户端需要。
   - 安装后确认 `npm` 可用。
3. Git for Windows

## 初始化

```powershell
git clone https://github.com/RrcioElise/fanqie-novel-lab.git
cd fanqie-novel-lab
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
```

`Set-ExecutionPolicy -Scope Process` 只影响当前 PowerShell 窗口，关闭窗口后失效。

## 启动 Web UI

```powershell
.\scripts\run_app.ps1
```

默认地址：

```text
http://127.0.0.1:8501
```

指定端口：

```powershell
.\scripts\run_app.ps1 -Port 8502
```

## 启动桌面客户端

```powershell
.\scripts\run_electron.ps1
```

第一次启动会在 `electron-client\node_modules` 安装 Electron 依赖。

## 模型配置

启动后进入：

```text
项目设置 → 模型
```

支持：

- OpenAI-compatible 中转站
- One API / New API
- OpenRouter
- Ollama / LM Studio 本地服务
- Claude CLI

本地配置会写入 `data\config\model_profiles.json`，默认不会提交到 Git。

## 常见问题

### PowerShell 提示禁止运行脚本

在当前窗口临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后重新运行脚本。

### 找不到 python

重新安装 Python，并勾选 **Add python.exe to PATH**。也可以安装 Python Launcher，让 `py -3` 可用。

### 找不到 npm

安装 Node.js LTS，安装后重新打开 PowerShell。

### 端口 8501 被占用

```powershell
.\scripts\run_app.ps1 -Port 8502
.\scripts\run_electron.ps1 -Port 8502
```

### 中文显示异常

脚本会设置 `PYTHONUTF8=1`。如果终端仍有乱码，建议使用 Windows Terminal 或 PowerShell 7。
