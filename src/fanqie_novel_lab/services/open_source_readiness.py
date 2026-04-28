from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from fanqie_novel_lab.config import PROJECT_ROOT


@dataclass(frozen=True)
class ReadinessItem:
    category: str
    item: str
    status: str
    detail: str
    path: str = ""


ESSENTIAL_FILES: tuple[tuple[str, str], ...] = (
    ("README.md", "项目入口、功能说明和快速开始"),
    ("LICENSE", "开源许可证"),
    (".gitignore", "忽略本地密钥、数据库、生成物和依赖缓存"),
    (".env.example", "环境变量模板，不能含真实密钥"),
    ("pyproject.toml", "Python 包元数据和依赖声明"),
)

COMMUNITY_FILES: tuple[tuple[str, str], ...] = (
    ("CONTRIBUTING.md", "贡献指南"),
    ("CODE_OF_CONDUCT.md", "社区行为准则"),
    ("SECURITY.md", "安全报告流程"),
    ("SUPPORT.md", "支持渠道和提问方式"),
    ("CHANGELOG.md", "版本更新记录"),
    ("ROADMAP.md", "后续路线图"),
)

GITHUB_FILES: tuple[tuple[str, str], ...] = (
    (".github/PULL_REQUEST_TEMPLATE.md", "PR 模板"),
    (".github/ISSUE_TEMPLATE/bug_report.yml", "Bug issue 表单"),
    (".github/ISSUE_TEMPLATE/feature_request.yml", "Feature issue 表单"),
    (".github/ISSUE_TEMPLATE/question.yml", "Question issue 表单"),
    (".github/workflows/ci.yml", "CI 工作流"),
    (".github/dependabot.yml", "依赖更新检查"),
)

DOC_FILES: tuple[tuple[str, str], ...] = (
    ("docs/ARCHITECTURE.md", "架构说明"),
    ("docs/CONFIGURATION.md", "配置指南"),
    ("docs/WORKFLOW.md", "创作工作流"),
    ("docs/DEVELOPMENT.md", "开发者指南"),
    ("docs/TROUBLESHOOTING.md", "常见问题排查"),
    ("docs/DATA_POLICY.md", "数据与本地文件说明"),
    ("docs/RELEASE.md", "发版流程"),
    ("docs/OPEN_SOURCE_CHECKLIST.md", "上传前检查清单"),
)

SENSITIVE_OR_LOCAL_PATHS: tuple[tuple[str, str], ...] = (
    (".env", "真实环境变量/密钥"),
    (".env.local", "本地环境变量"),
    (".venv", "Python 虚拟环境"),
    (".npm-cache", "npm 缓存"),
    ("electron-client/node_modules", "Electron 依赖目录"),
    ("data/config/model_profiles.json", "本机模型配置，可能包含中转地址或密钥"),
    ("data/db/fanqie_novel_lab.sqlite3", "本地 SQLite 数据库"),
    ("logs/electron.log", "本地日志"),
    ("outputs", "生成的大纲、章节、审核报告和上传包"),
    ("src/fanqie_novel_lab.egg-info", "本地 Python 构建产物"),
)


def _exists(root: Path, rel_path: str) -> bool:
    return (root / rel_path).exists()


def _read_gitignore_patterns(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []
    patterns: list[str] = []
    for raw in gitignore.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _pattern_matches(pattern: str, rel_path: str, is_dir: bool) -> bool:
    normalized = rel_path.strip("/")
    negated = pattern.startswith("!")
    if negated:
        pattern = pattern[1:]
    pattern = pattern.strip("/")
    if not pattern:
        return False

    candidates = [normalized]
    if is_dir:
        candidates.append(f"{normalized}/")

    if pattern.endswith("/"):
        prefix = pattern.strip("/")
        return normalized == prefix or normalized.startswith(prefix + "/")

    if "/" not in pattern:
        parts = normalized.split("/")
        return any(fnmatch(part, pattern) for part in parts)

    if any(fnmatch(candidate, pattern) for candidate in candidates):
        return True
    return False


def is_gitignored(rel_path: str, *, root: Path | None = None) -> bool:
    """Best-effort .gitignore matcher for the app UI.

    It intentionally avoids shelling out to `git check-ignore` because the project
    may not be initialized as a Git repository yet.
    """

    root = root or PROJECT_ROOT
    path = root / rel_path
    ignored = False
    for pattern in _read_gitignore_patterns(root):
        negated = pattern.startswith("!")
        if _pattern_matches(pattern, rel_path, path.is_dir()):
            ignored = not negated
    return ignored


def _file_items(category: str, files: Iterable[tuple[str, str]], root: Path) -> list[ReadinessItem]:
    items: list[ReadinessItem] = []
    for rel_path, detail in files:
        ok = _exists(root, rel_path)
        items.append(
            ReadinessItem(
                category=category,
                item=rel_path,
                status="pass" if ok else "fail",
                detail=detail if ok else f"缺失：{detail}",
                path=rel_path,
            )
        )
    return items


def scan_open_source_readiness(root: Path | None = None) -> list[ReadinessItem]:
    root = root or PROJECT_ROOT
    root = root.resolve()
    items: list[ReadinessItem] = []
    items.extend(_file_items("必备文件", ESSENTIAL_FILES, root))
    items.extend(_file_items("社区文件", COMMUNITY_FILES, root))
    items.extend(_file_items("GitHub 配置", GITHUB_FILES, root))
    items.extend(_file_items("项目文档", DOC_FILES, root))

    for rel_path, detail in SENSITIVE_OR_LOCAL_PATHS:
        exists = (root / rel_path).exists()
        if rel_path == "outputs" and exists:
            generated = [
                path
                for path in (root / rel_path).rglob("*")
                if path.is_file() and path.name != ".gitkeep"
            ]
            not_ignored = [
                str(path.relative_to(root))
                for path in generated
                if not is_gitignored(str(path.relative_to(root)), root=root)
            ]
            if not_ignored:
                preview = ", ".join(not_ignored[:3])
                items.append(
                    ReadinessItem(
                        "敏感文件",
                        rel_path,
                        "fail",
                        f"发现未忽略的生成物：{preview}",
                        rel_path,
                    )
                )
            else:
                items.append(
                    ReadinessItem(
                        "敏感文件",
                        rel_path,
                        "pass",
                        f"存在 {len(generated)} 个本地生成物，均已由 .gitignore 规则保护",
                        rel_path,
                    )
                )
            continue

        ignored = is_gitignored(rel_path, root=root)
        if exists and ignored:
            status = "pass"
            message = f"存在于本机，但已被 .gitignore 忽略：{detail}"
        elif exists and not ignored:
            status = "fail"
            message = f"存在且未确认忽略，上传前必须处理：{detail}"
        else:
            status = "pass"
            message = f"未发现本地敏感/生成路径：{detail}"
        items.append(ReadinessItem("敏感文件", rel_path, status, message, rel_path))

    return items


def readiness_summary(items: list[ReadinessItem]) -> dict[str, int | str]:
    passed = sum(1 for item in items if item.status == "pass")
    failed = sum(1 for item in items if item.status == "fail")
    warnings = sum(1 for item in items if item.status == "warn")
    score = round((passed / max(1, len(items))) * 100)
    verdict = "ready" if failed == 0 else "blocked"
    return {"score": score, "pass": passed, "warn": warnings, "fail": failed, "verdict": verdict}


def readiness_rows(items: list[ReadinessItem]) -> list[dict[str, str]]:
    labels = {"pass": "✅ 通过", "warn": "⚠️ 注意", "fail": "❌ 待处理"}
    return [
        {
            "类别": item.category,
            "项目": item.item,
            "状态": labels.get(item.status, item.status),
            "说明": item.detail,
        }
        for item in items
    ]


def readiness_json(items: list[ReadinessItem]) -> dict[str, object]:
    return {"summary": readiness_summary(items), "items": [asdict(item) for item in items]}


def readiness_markdown(items: list[ReadinessItem]) -> str:
    summary = readiness_summary(items)
    lines = [
        "# Open Source Readiness Report",
        "",
        f"- Score: {summary['score']}/100",
        f"- Verdict: {summary['verdict']}",
        f"- Pass: {summary['pass']}",
        f"- Fail: {summary['fail']}",
        "",
        "| Category | Item | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        status = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(item.status, item.status.upper())
        detail = item.detail.replace("|", "\\|")
        lines.append(f"| {item.category} | `{item.item}` | {status} | {detail} |")
    return "\n".join(lines) + "\n"
