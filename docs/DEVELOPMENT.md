# Development Guide

## 本地开发

```bash
git clone https://github.com/<your-name>/fanqie-novel-lab.git
cd fanqie-novel-lab
bash scripts/setup.sh
bash scripts/run_app.sh
```

Electron 客户端：

```bash
bash scripts/run_electron.sh
```

## 常用命令

```bash
# Python 语法检查
python -m py_compile $(find src -name '*.py')

# 单元测试
python -m unittest discover -s tests

# 开源发布体检
fanqie-lab open-source-check
```

## 模块边界

- `app.py`：只处理交互和展示，复杂业务放到 `services/`。
- `services/`：大纲、章节、审核、发布、开源体检等业务逻辑。
- `crawler/`：只处理公开元数据采集和解析。
- `schemas.py`：Pydantic 数据模型，跨 UI/CLI/服务复用。

## UI 约定

- 页面说明保持短句，复杂说明放文档。
- 尽量使用 tab、弹窗、紧凑表格，避免堆大卡片。
- 所有下载/保存按钮要说明真实数据来源。

## 数据约定

- 生成物写入 `outputs/`，默认不提交。
- 本机配置写入 `data/config/`，默认不提交。
- 公开元数据写入 SQLite，默认不提交。
