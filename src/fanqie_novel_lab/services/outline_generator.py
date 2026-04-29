from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..config import OUTLINE_DIR
from ..db import save_outline
from ..llm import chat_json, require_llm_configured
from ..prompts import OUTLINE_SYSTEM, OUTLINE_USER, POLISH_SYSTEM, POLISH_USER
from ..schemas import NovelOutline, OutlineReview, TopicBrief, TrendReport


def generate_outline(topic: TopicBrief, trend: TrendReport) -> NovelOutline:
    require_llm_configured()
    user = OUTLINE_USER.format(
        topic_json=topic.model_dump_json(indent=2),
        trend_json=trend.model_dump_json(indent=2),
    )
    data = chat_json(OUTLINE_SYSTEM, user)
    return NovelOutline(**data)


def polish_outline(outline: NovelOutline, review: OutlineReview) -> NovelOutline:
    require_llm_configured()
    user = POLISH_USER.format(
        review_json=review.model_dump_json(indent=2),
        outline_json=outline.model_dump_json(indent=2),
    )
    data = chat_json(POLISH_SYSTEM, user)
    return NovelOutline(**data)


def outline_to_markdown(outline: NovelOutline) -> str:
    lines: list[str] = []
    lines.append(f"# {outline.title_candidates[0] if outline.title_candidates else '未命名大纲'}")
    lines.append("")
    lines.append(f"**一句话卖点：** {outline.one_line_pitch}")
    lines.append("")
    lines.append("## 书名候选")
    lines.extend(f"- {x}" for x in outline.title_candidates)
    lines.append("")
    lines.append("## 核心卖点")
    lines.extend(f"- {x}" for x in outline.selling_points)
    lines.append("")
    lines.append("## 世界观")
    lines.append(outline.world_setting)
    lines.append("")
    lines.append("## 主角")
    for k, v in outline.protagonist.items():
        lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("## 金手指/核心钩子规则")
    lines.extend(f"- {x}" for x in outline.power_system_or_hook_rules)
    lines.append("")
    lines.append("## 卷纲")
    for vol in outline.volume_plan:
        lines.append(f"### {vol.get('volume', '')}")
        for k, v in vol.items():
            if k != "volume":
                lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("## 前 10 章")
    for ch in outline.first_10_chapters:
        lines.append(f"### 第 {ch.get('chapter', '')} 章：{ch.get('title', '')}")
        for k in ["goal", "conflict", "twist", "hook_type", "foreshadowing", "reversal_logic", "ending_hook"]:
            lines.append(f"- **{k}**：{ch.get(k, '')}")
    lines.append("")
    lines.append("## 风险提醒")
    lines.extend(f"- {x}" for x in outline.risk_notes)
    if outline.revision_notes:
        lines.append("")
        lines.append("## 润色记录")
        lines.extend(f"- {x}" for x in outline.revision_notes)
    return "\n".join(lines).strip() + "\n"


def save_outline_files(outline: NovelOutline, genre: str) -> tuple[Path, Path, int]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = (outline.title_candidates[0] if outline.title_candidates else genre).replace("/", "-")[:40]
    json_path = OUTLINE_DIR / f"{stamp}_{safe_title}.json"
    md_path = OUTLINE_DIR / f"{stamp}_{safe_title}.md"
    payload = outline.model_dump()
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(outline_to_markdown(outline), encoding="utf-8")
    outline_id = save_outline(safe_title, genre, payload)
    return json_path, md_path, outline_id
