# Security Policy

## 支持版本

当前仅维护 `main` 分支和最新发布版本。

## 报告安全问题

请不要在公开 issue 中贴 API Key、Cookie、账户信息、数据库、日志或未发布作品正文。

建议报告内容：

- 受影响版本或 commit
- 复现步骤
- 影响范围
- 最小化的日志片段（请先脱敏）

如果仓库尚未开启 GitHub 私密漏洞报告，请通过维护者在 README 或 GitHub profile 中提供的联系方式提交。

## 本地敏感文件

这些文件默认不应提交：

- `.env`
- `data/config/model_profiles.json`
- `data/db/*.sqlite3`
- `outputs/`
- `logs/`
