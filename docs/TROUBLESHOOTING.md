# Troubleshooting

## Streamlit 启动失败

macOS / Linux:

```bash
bash scripts/setup.sh
bash scripts/run_app.sh
```

Windows:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
.\scripts\run_app.ps1
```

如果端口被占用，可先停止旧进程或改用：

```bash
streamlit run src/fanqie_novel_lab/app.py --server.port 8502
```

Windows:

```powershell
.\scripts\run_app.ps1 -Port 8502
```

## Electron 打不开页面

1. 先确认 Web UI 能打开：`http://127.0.0.1:8501`。
2. 删除旧依赖后重装：

```bash
rm -rf electron-client/node_modules
bash scripts/run_electron.sh
```

Windows:

```powershell
Remove-Item electron-client\node_modules -Recurse -Force
.\scripts\run_electron.ps1
```

## Windows PowerShell 禁止运行脚本

如果出现 `running scripts is disabled on this system`：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

该命令只影响当前 PowerShell 窗口。

## 模型没有返回

- 检查 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。
- OpenAI-compatible 网关需要 `/v1` 结尾时请补齐。
- 本地 Ollama / LM Studio 请先确认服务已启动。
- Claude CLI 桥接请确认本机 CLI 可直接调用对应模型。

## 正文字数偏差

章节生成会把目标字数写入 prompt，并在结果中记录 `target_words` 和 `actual_length`。模型可能仍有自然偏差；建议：

- 先生成单章；
- 在章节工坊里继续扩写/润色；
- 用章节审核检查是否跑题或节奏变形。

## 上传前担心误提交隐私文件

```bash
fanqie-lab open-source-check
git status --ignored
git add -n .
```

确认 `.env`、数据库、`outputs/`、日志、模型配置没有进入 Git 暂存区。
