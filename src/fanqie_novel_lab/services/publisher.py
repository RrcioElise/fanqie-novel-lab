from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import PUBLISH_PACKAGE_DIR, PUBLISH_WORK_DIR
from ..schemas import ChapterDraft, NovelOutline
from .chapter_generator import chapter_to_markdown, content_length
from .outline_generator import outline_to_markdown

FANQIE_WRITER_ZONE_URL = "https://fanqienovel.com/writer/zone/"


class WorkProfile(BaseModel):
    id: str
    platform: str = "番茄小说"
    platform_url: str = FANQIE_WRITER_ZONE_URL
    title: str = ""
    author_pen_name: str = ""
    category: str = ""
    audience: str = ""
    tags: list[str] = Field(default_factory=list)
    intro: str = ""
    status: str = "本地筹备"
    fanqie_work_id: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class PublishPackage(BaseModel):
    id: str
    work_id: str = ""
    platform: str = "番茄小说"
    platform_url: str = FANQIE_WRITER_ZONE_URL
    work_title: str = ""
    chapter_no: int = 1
    chapter_title: str = ""
    content: str = ""
    source_chapter_path: str = ""
    upload_status: str = "待上传"
    operator_notes: str = ""
    preflight: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def length(self) -> int:
        return content_length(self.content)


def now_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def safe_name(value: str, fallback: str = "item") -> str:
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_.-]+", "_", value or fallback).strip("_")
    return safe[:60] or fallback


def work_path(work_id: str) -> Path:
    return PUBLISH_WORK_DIR / f"{safe_name(work_id)}.json"


def package_path(package_id: str) -> Path:
    return PUBLISH_PACKAGE_DIR / f"{safe_name(package_id)}.json"


def list_work_profiles() -> list[WorkProfile]:
    items: list[WorkProfile] = []
    for path in sorted(PUBLISH_WORK_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            items.append(WorkProfile(**json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return items


def load_work_profile(path_or_id: str | Path) -> WorkProfile:
    path = Path(path_or_id)
    if not path.exists():
        path = work_path(str(path_or_id))
    return WorkProfile(**json.loads(path.read_text(encoding="utf-8")))


def save_work_profile(work: WorkProfile) -> Path:
    work.updated_at = datetime.now().isoformat(timespec="seconds")
    path = work_path(work.id)
    path.write_text(work.model_dump_json(indent=2), encoding="utf-8")
    return path


def work_from_outline(outline: NovelOutline, *, author_pen_name: str = "") -> WorkProfile:
    title = outline.title_candidates[0] if outline.title_candidates else "未命名作品"
    tags: list[str] = []
    for item in [outline.genre_positioning, *outline.selling_points[:5]]:
        if item:
            tags.append(str(item)[:18])
    return WorkProfile(
        id=now_id("work"),
        title=title,
        author_pen_name=author_pen_name,
        category=outline.genre_positioning,
        audience=outline.target_reader,
        tags=tags,
        intro=outline.one_line_pitch,
        notes="由当前大纲生成的本地作品档案。",
    )


def list_publish_packages() -> list[PublishPackage]:
    items: list[PublishPackage] = []
    for path in sorted(PUBLISH_PACKAGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            items.append(PublishPackage(**json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return items


def load_publish_package(path_or_id: str | Path) -> PublishPackage:
    path = Path(path_or_id)
    if not path.exists():
        path = package_path(str(path_or_id))
    return PublishPackage(**json.loads(path.read_text(encoding="utf-8")))


def validate_publish_package(pkg: PublishPackage, *, min_words: int = 1000, max_words: int = 8000) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, message: str, severity: str = "error") -> None:
        checks.append({"项目": name, "通过": bool(ok), "级别": "通过" if ok else severity, "说明": message})

    length = pkg.length
    add("章节标题", bool(pkg.chapter_title.strip()), "章节标题不能为空。")
    add("正文内容", bool(pkg.content.strip()), "正文不能为空。")
    add("字数下限", length >= min_words, f"当前 {length} 字，建议不少于 {min_words} 字。", "warning")
    add("字数上限", length <= max_words, f"当前 {length} 字，建议不超过 {max_words} 字，过长可拆章。", "warning")
    add("无 Markdown 代码块", "```" not in pkg.content, "正文不应包含 Markdown 代码块标记。", "warning")
    add("无 AI 说明口吻", not re.search(r"作为AI|根据你的要求|以下是|我将为你", pkg.content), "正文不应包含模型说明口吻。", "warning")
    add("段落密度", len([x for x in pkg.content.splitlines() if x.strip()]) >= 6, "建议有足够自然段，方便后台编辑和读者阅读。", "warning")
    add("章末钩子", bool(re.search(r"[？?!！。…]$", pkg.content.strip()[-12:] if pkg.content else "")), "章末建议有明确情绪、问题或反转落点。", "warning")
    return checks


def package_from_chapter(chapter: ChapterDraft, work: WorkProfile | None = None, source_path: str = "") -> PublishPackage:
    work_title = work.title if work else chapter.outline_title
    pkg = PublishPackage(
        id=now_id("pkg"),
        work_id=work.id if work else "",
        work_title=work_title or chapter.outline_title,
        chapter_no=int(chapter.chapter_no),
        chapter_title=chapter.title,
        content=chapter.content.strip(),
        source_chapter_path=source_path,
        operator_notes="由章节工坊生成的待上传包。最终发布前请在番茄作家后台人工确认。",
    )
    pkg.preflight = validate_publish_package(pkg)
    return pkg


def save_publish_package(pkg: PublishPackage) -> tuple[Path, Path, Path]:
    pkg.updated_at = datetime.now().isoformat(timespec="seconds")
    if not pkg.preflight:
        pkg.preflight = validate_publish_package(pkg)
    base = f"{pkg.id}_{safe_name(pkg.work_title or '作品')}_第{pkg.chapter_no:03d}章"
    json_path = PUBLISH_PACKAGE_DIR / f"{base}.json"
    txt_path = PUBLISH_PACKAGE_DIR / f"{base}.txt"
    md_path = PUBLISH_PACKAGE_DIR / f"{base}.md"
    json_path.write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    txt_path.write_text(package_to_txt(pkg), encoding="utf-8")
    md_path.write_text(package_to_markdown(pkg), encoding="utf-8")
    return json_path, txt_path, md_path


def update_package_status(pkg: PublishPackage, status: str, notes: str = "") -> Path:
    pkg.upload_status = status
    if notes.strip():
        pkg.operator_notes = notes.strip()
    pkg.updated_at = datetime.now().isoformat(timespec="seconds")
    path = package_path(pkg.id)
    if not path.exists():
        # Fall back to matching generated package file prefix.
        matches = list(PUBLISH_PACKAGE_DIR.glob(f"{safe_name(pkg.id)}*.json"))
        path = matches[0] if matches else path
    path.write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    return path


def package_to_txt(pkg: PublishPackage) -> str:
    title = pkg.chapter_title.strip() or f"第{pkg.chapter_no}章"
    return f"{title}\n\n{pkg.content.strip()}\n"


def package_to_markdown(pkg: PublishPackage) -> str:
    failed = [x for x in pkg.preflight if not x.get("通过")]
    checks = "\n".join(f"- {'✅' if c.get('通过') else '⚠️'} {c.get('项目')}：{c.get('说明')}" for c in pkg.preflight)
    return f"""# {pkg.work_title or '未命名作品'} · 第 {pkg.chapter_no} 章上传包

- 平台：{pkg.platform}
- 后台：{pkg.platform_url}
- 状态：{pkg.upload_status}
- 字数：{pkg.length}
- 风险项：{len(failed)}
- 生成时间：{pkg.created_at}

## 提交前检查

{checks or '暂无检查项。'}

## 章节标题

{pkg.chapter_title}

## 正文

{pkg.content.strip()}
"""
