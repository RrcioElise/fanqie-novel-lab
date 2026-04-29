# Fanqie Novel Lab

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Electron](https://img.shields.io/badge/Desktop-Electron-47848F?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

官网介绍页：[https://novel.zns.cc](https://novel.zns.cc)

Fanqie Novel Lab 是一个面向中文网文创作流程的本地工作台：采集公开榜单元数据、生成原创大纲、人审润色、避撞审查、章节生成、章节对纲审核、发布包管理，并支持 OpenAI-compatible API 与 Claude CLI 等模型接入。

> 项目定位：辅助原创创作和本地编辑工作流，不是自动搬运/洗稿工具。

## 功能概览

| 模块 | 能力 |
| --- | --- |
| 数据花园 | 采集/导入公开元数据，管理本地 SQLite 样本库 |
| 题材与大纲 | 根据题材 brief、趋势报告和创作约束生成长篇大纲 |
| 人审润色 | 按原创性、钩子、节奏、人物代入等维度打分并润色大纲 |
| 避撞审查 | 基于本地元数据检查题材、简介、钩子和关键词相似风险 |
| 章节工坊 | 分章节、分场景生成正文；支持人工编辑和 AI 润色 |
| 章节审核 | 对照大纲检查跑题；新增 AI 味检测、伏笔台账和有迹可循反转审查 |
| 发布中心 | 管理作品档案、章节上传包、发布队列、发布自动化清单和番茄作家后台助手 |
| 模型配置 | 支持 OpenAI-compatible 网关、本地 Ollama/LM Studio、Claude CLI |

## 快速开始

### macOS / Linux

```bash
git clone https://github.com/RrcioElise/fanqie-novel-lab.git
cd fanqie-novel-lab
bash scripts/setup.sh
bash scripts/run_app.sh
```

### Windows 10/11

先安装：

- Python 3.10+（安装时勾选 **Add python.exe to PATH**）
- Node.js LTS（用于 Electron 桌面客户端）
- Git for Windows

在 PowerShell 中运行：

```powershell
git clone https://github.com/RrcioElise/fanqie-novel-lab.git
cd fanqie-novel-lab
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
.\scripts\run_app.ps1
```

打开本地 Web UI：

```text
http://127.0.0.1:8501
```

桌面客户端：

```bash
bash scripts/run_electron.sh
```

Windows 桌面客户端：

```powershell
.\scripts\run_electron.ps1
```

第一次启动 Electron 会在 `electron-client/` 下安装依赖。

## 模型配置

复制环境变量模板：

```bash
cp .env.example .env
```

也可以在客户端顶部的“项目设置 → 模型”中配置：

- DeepSeek / OpenAI / OpenRouter
- Ollama 本地模型
- LM Studio 本地模型
- 硅基流动、火山方舟等 OpenAI-compatible 接口
- Claude CLI 本机模型，例如 `mimo-v2.5-pro`

示例：

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=
LLM_TEMPERATURE=0.75
LLM_TIMEOUT_SECONDS=120
```

## CLI 示例

```bash
# 初始化数据库
fanqie-lab init-db

# 查看公开榜单分类
fanqie-lab rank-categories

# 采集榜单元数据
fanqie-lab crawl-rank --category-id 262 --gender 1 --rank-mold 1 --limit 50

# 导入 CSV 元数据
fanqie-lab import-csv sample_data/fanqie_metadata_template.csv

# 生成大纲
fanqie-lab generate-outline \
  --genre "都市脑洞" \
  --audience "男频" \
  --core-hook "底层主角能看到他人隐藏信息" \
  --style "爽文、节奏快、三章内出爆点"

# 生成正文，指定起始章节、章数、目标字数
fanqie-lab generate-chapter outputs/outlines/<outline>.json \
  --chapter-no 1 \
  --count 1 \
  --target-words 4500

# 对照大纲审核单章
fanqie-lab audit-chapter outputs/outlines/<outline>.json outputs/chapters/<chapter>.json

# 开源发布体检
fanqie-lab open-source-check
```

## 项目结构

```text
fanqie-novel-lab/
  src/fanqie_novel_lab/
    app.py                    # Streamlit 客户端
    cli.py                    # 命令行入口
    config.py                 # 目录和环境配置
    db.py                     # SQLite 元数据存储
    llm.py                    # 模型调用适配
    model_profiles.py         # 多模型配置与切换
    schemas.py                # Pydantic 数据结构
    crawler/                  # 公开元数据采集
    services/                 # 大纲、章节、审核、发布等业务逻辑
  electron-client/            # 桌面客户端壳
  sample_data/                # CSV 模板
  docs/                       # 架构、工作流和开源说明
  scripts/                    # 安装和启动脚本
  outputs/                    # 本地生成物，默认不提交 Git
```

## 本地生成物

以下目录用于本地运行，不建议提交到公开仓库：

- `data/db/*.sqlite3`
- `data/config/model_profiles.json`
- `outputs/`
- `logs/`
- `.env`
- `.venv/`
- `electron-client/node_modules/`

`.gitignore` 已默认忽略这些文件。

## 开发验证

```bash
python -m py_compile $(find src -name '*.py')
python -m unittest discover -s tests
```

## 文档

- [工作流说明](docs/WORKFLOW.md)
- [架构说明](docs/ARCHITECTURE.md)
- [配置指南](docs/CONFIGURATION.md)
- [开发者指南](docs/DEVELOPMENT.md)
- [Windows 使用指南](docs/WINDOWS.md)
- [排查指南](docs/TROUBLESHOOTING.md)
- [数据与本地文件说明](docs/DATA_POLICY.md)
- [发版指南](docs/RELEASE.md)
- [FAQ](docs/FAQ.md)
- [开源发布清单](docs/OPEN_SOURCE_CHECKLIST.md)
- [路线图](ROADMAP.md)
- [更新日志](CHANGELOG.md)

## 贡献

欢迎提交 issue、功能建议和 PR。请先阅读：

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## License

MIT License. See [LICENSE](LICENSE).
