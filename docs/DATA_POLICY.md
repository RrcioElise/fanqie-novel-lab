# Data & Local Files

## 本地文件类型

| 路径 | 内容 | 是否提交 |
| --- | --- | --- |
| `.env` | API Key 和模型环境变量 | 否 |
| `data/config/model_profiles.json` | UI 模型配置和中转地址 | 否 |
| `data/db/*.sqlite3` | 本地公开元数据样本库 | 否 |
| `outputs/` | 大纲、章节、审核报告、发布包 | 否 |
| `logs/` | 本地运行日志 | 否 |
| `sample_data/` | 示例 CSV 模板 | 是 |

## 数据来源

项目面向公开元数据分析和原创写作流程管理。建议只保存榜单、分类、标题、作者、简介、标签、热度、评分等公开展示字段。

## 分享 issue 时

请先脱敏：

- API Key / Token / Cookie
- 未公开作品正文
- 平台账户信息
- 本地绝对路径中不想公开的用户名
