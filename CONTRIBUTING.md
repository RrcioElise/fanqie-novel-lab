# Contributing

感谢你愿意改进 Fanqie Novel Lab。

## 开发环境

```bash
git clone https://github.com/<your-name>/fanqie-novel-lab.git
cd fanqie-novel-lab
bash scripts/setup.sh
bash scripts/run_app.sh
```

## 提交前检查

```bash
python -m py_compile $(find src -name '*.py')
python -m unittest discover -s tests
```

## PR 建议

1. 一个 PR 只解决一个主题。
2. UI 改动请附截图或说明影响页面。
3. 新增业务逻辑请补充测试或 CLI 示例。
4. 不提交 `.env`、数据库、生成章节、模型配置和日志。
5. 涉及采集逻辑时，请说明数据来源、字段范围和速率限制。

## 代码风格

- Python 代码保持类型标注和清晰函数边界。
- UI 文案尽量短，复杂说明放到 docs。
- 生成物写入 `outputs/`，配置写入 `data/config/`。

## Issue 类型

- Bug：描述复现步骤、实际结果、期望结果、日志。
- Feature：描述目标用户、工作流、输入输出。
- Docs：指出页面或章节位置。
