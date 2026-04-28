from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import CHAPTER_DIR
from ..llm import chat_json, chat_text, require_llm_configured
from ..prompts import (
    CHAPTER_CONTINUE_SYSTEM,
    CHAPTER_CONTINUE_USER,
    CHAPTER_CONDENSE_SYSTEM,
    CHAPTER_CONDENSE_USER,
    CHAPTER_EXPAND_SYSTEM,
    CHAPTER_EXPAND_USER,
    CHAPTER_POLISH_SYSTEM,
    CHAPTER_POLISH_USER,
    CHAPTER_SEGMENT_SYSTEM,
    CHAPTER_SEGMENT_USER,
    CHAPTER_SYSTEM,
    CHAPTER_USER,
)
from ..schemas import ChapterDraft, ChapterReview, NovelOutline


def _safe_name(value: str, fallback: str = "chapter") -> str:
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_.-]+", "_", value or fallback).strip("_")
    return safe[:50] or fallback


def outline_title(outline: NovelOutline) -> str:
    return outline.title_candidates[0] if outline.title_candidates else "未命名大纲"


def content_length(text: str) -> int:
    """Approximate Chinese webnovel word count by non-whitespace characters."""
    return len(re.sub(r"\s+", "", text or ""))


def min_content_length(target_words: int) -> int:
    # Allow small variance, but avoid the common failure where a 4500-word
    # request silently becomes a 2500-ish chapter.
    return max(400, int(int(target_words) * 0.90))


def max_content_length(target_words: int) -> int:
    return max(700, int(int(target_words) * 1.18))


def _clean_prose(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:text|markdown|md)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^\s*(?:第[一二三四五六七八九十\d]+[个段落场景幕节：:、.\s-]+)+", "", text)
    text = re.sub(r"^\s*(?:正文片段|新增正文|扩写内容|以下是.*?正文)[:：]\s*", "", text)
    return text.strip()


def compact_outline_context(outline: NovelOutline) -> str:
    data = {
        "title": outline_title(outline),
        "one_line_pitch": outline.one_line_pitch,
        "selling_points": outline.selling_points,
        "genre_positioning": outline.genre_positioning,
        "world_setting": outline.world_setting,
        "protagonist": outline.protagonist,
        "key_characters": outline.key_characters[:6],
        "power_system_or_hook_rules": outline.power_system_or_hook_rules,
        "long_arc": outline.long_arc[:8],
        "recurring_hooks": outline.recurring_hooks[:8],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def scene_task(scene_index: int, scene_count: int, chapter_plan: dict[str, Any]) -> str:
    goal = chapter_plan.get("goal", "推进本章目标")
    conflict = chapter_plan.get("conflict", "制造外部冲突和主角选择")
    twist = chapter_plan.get("twist", "加入信息差或反转")
    ending_hook = chapter_plan.get("ending_hook", "章末留钩子")
    if scene_count <= 1:
        return f"完整推进本章：目标={goal}；冲突={conflict}；反转={twist}；结尾={ending_hook}"
    if scene_index == 1:
        return f"开篇迅速入戏，建立压力源和主角处境；埋入本章目标：{goal}"
    if scene_index == scene_count:
        return f"收束本章冲突，给出反转或更大危机，最后落到章末钩子：{ending_hook}"
    if scene_index == scene_count - 1:
        return f"把冲突推到最紧，加入关键反转：{twist}；但不要提前完结。"
    return f"持续升级核心冲突：{conflict}；用对白、动作和信息差推进。"


def chapter_plan_from_outline(outline: NovelOutline, chapter_no: int) -> dict[str, Any]:
    for item in outline.first_10_chapters:
        try:
            if int(item.get("chapter", -1)) == int(chapter_no):
                return dict(item)
        except Exception:
            continue

    # If the outline only has the first 10 chapters, infer later chapter intent
    # from the volume plan instead of inventing a fake saved plan.
    for volume in outline.volume_plan:
        chapters = str(volume.get("chapters", ""))
        numbers = [int(x) for x in re.findall(r"\d+", chapters)]
        if len(numbers) >= 2 and numbers[0] <= chapter_no <= numbers[-1]:
            return {
                "chapter": chapter_no,
                "title": f"第{chapter_no}章",
                "goal": volume.get("goal", ""),
                "conflict": volume.get("main_conflict", ""),
                "twist": "围绕本卷目标推进一个新的阶段性反转",
                "ending_hook": volume.get("ending_hook", ""),
            }

    return {
        "chapter": chapter_no,
        "title": f"第{chapter_no}章",
        "goal": "承接主线，推进主角阶段目标",
        "conflict": "让主角在代价、现实压力和外部阻力之间做选择",
        "twist": "章中给出信息差或规则反转",
        "ending_hook": "用新的危机或机会收尾",
    }


def generate_chapter(
    outline: NovelOutline,
    chapter_no: int = 1,
    target_words: int = 2500,
    previous_context: str = "",
    requirements: str = "",
) -> ChapterDraft:
    require_llm_configured()
    target_words = int(target_words)
    if target_words >= 3000:
        return generate_chapter_segmented(outline, chapter_no, target_words, previous_context, requirements)
    min_words = min_content_length(target_words)
    chapter_plan = chapter_plan_from_outline(outline, chapter_no)
    user = CHAPTER_USER.format(
        outline_json=outline.model_dump_json(indent=2),
        chapter_plan_json=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
        previous_context=previous_context.strip() or "无。请按大纲从本章自然开始。",
        requirements=requirements.strip() or "番茄小说节奏，强冲突，少解释，多动作和对话，章末留钩子。",
        target_words=target_words,
        min_target_words=min_words,
    )
    data = chat_json(CHAPTER_SYSTEM, user)
    data.setdefault("outline_title", outline_title(outline))
    data.setdefault("chapter_no", chapter_no)
    data.setdefault("title", chapter_plan.get("title") or f"第{chapter_no}章")
    chapter = ChapterDraft(**data)
    return ensure_chapter_length(outline, chapter, target_words)


def generate_chapter_segmented(
    outline: NovelOutline,
    chapter_no: int,
    target_words: int,
    previous_context: str = "",
    requirements: str = "",
) -> ChapterDraft:
    require_llm_configured()
    target_words = int(target_words)
    chapter_plan = chapter_plan_from_outline(outline, chapter_no)
    title = str(chapter_plan.get("title") or f"第{chapter_no}章")
    outline_context = compact_outline_context(outline)
    scene_count = max(3, min(6, (target_words + 1199) // 1200))
    # Models routinely overshoot Chinese prose segment lengths. Ask for a
    # smaller per-scene target and enforce an upper bound in the prompt.
    segment_target = max(650, int(((target_words + scene_count - 1) // scene_count) * 0.68))
    segment_min = max(420, int(segment_target * 0.70))
    segment_max = max(760, int(segment_target * 1.25))
    segments: list[str] = []
    written = ""
    generation_notes = [
        f"长章节分段生成：目标 {target_words}，场景数 {scene_count}，单场景目标约 {segment_target}。",
        "已忽略大纲中可能存在的旧字数提示。",
    ]
    for idx in range(1, scene_count + 1):
        user = CHAPTER_SEGMENT_USER.format(
            chapter_no=chapter_no,
            chapter_title=title,
            scene_index=idx,
            scene_count=scene_count,
            outline_context=outline_context,
            chapter_plan_json=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
            requirements=requirements.strip() or "番茄小说节奏，强冲突，少解释，多动作和对话，章末留钩子。",
            previous_context=previous_context.strip() or "无。请按大纲从本章自然开始。",
            written_tail=written[-1200:] if written else "无，当前是本章开篇。",
            scene_task=scene_task(idx, scene_count, chapter_plan),
            segment_target=segment_target,
            segment_min=segment_min,
            segment_max=segment_max,
        )
        segment = _clean_prose(chat_text(CHAPTER_SEGMENT_SYSTEM, user))
        if segment:
            segments.append(segment)
            written = "\n\n".join(segments)
            generation_notes.append(f"场景 {idx}/{scene_count} 长度：{content_length(segment)}。")

    content = "\n\n".join(segments).strip()
    content = continue_until_target(
        outline=outline,
        chapter_plan=chapter_plan,
        content=content,
        target_words=target_words,
        previous_context=previous_context,
        requirements=requirements,
        generation_notes=generation_notes,
    )
    content = condense_if_too_long(chapter_plan, content, target_words, generation_notes)
    actual = content_length(content)
    return ChapterDraft(
        outline_title=outline_title(outline),
        chapter_no=chapter_no,
        title=title,
        pov="第三人称有限视角",
        chapter_goal=str(chapter_plan.get("goal") or ""),
        conflict=str(chapter_plan.get("conflict") or ""),
        content=content,
        ending_hook=str(chapter_plan.get("ending_hook") or ""),
        continuity_notes=[
            "下一章承接本章章末钩子继续推进。",
            "保持主角能力规则、代价和人物关系一致。",
            "继续检查正文长度与节奏，避免场景跳跃过快。",
        ],
        originality_notes=[
            "本章由原创大纲分场景生成，未抓取或复用番茄正文。",
            "分段围绕本章内部冲突推进，避免只套用通用爽文章法。",
            "后续仍建议使用避撞审查和人工编辑做最终把关。",
        ],
        next_chapter_seed=str(chapter_plan.get("ending_hook") or ""),
        target_words=target_words,
        actual_length=actual,
        generation_notes=generation_notes + [f"最终正文长度：{actual}。"],
    )


def condense_if_too_long(
    chapter_plan: dict[str, Any],
    content: str,
    target_words: int,
    generation_notes: list[str],
) -> str:
    current_len = content_length(content)
    max_words = max_content_length(target_words)
    if current_len <= max_words:
        return content
    user = CHAPTER_CONDENSE_USER.format(
        chapter_plan_json=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
        content=content,
        current_words=current_len,
        target_words=target_words,
        min_words=min_content_length(target_words),
        max_words=max_words,
    )
    condensed = _clean_prose(chat_text(CHAPTER_CONDENSE_SYSTEM, user))
    condensed_len = content_length(condensed)
    generation_notes.append(f"正文过长，已请求压缩：{current_len} -> {condensed_len}。")
    if condensed and min_content_length(target_words) <= condensed_len <= max_words:
        return condensed
    # If the model fails to condense into range, prefer the shorter complete
    # version when it is not below the minimum.
    if condensed and condensed_len >= min_content_length(target_words) and condensed_len < current_len:
        return condensed
    return content


def continue_until_target(
    outline: NovelOutline,
    chapter_plan: dict[str, Any],
    content: str,
    target_words: int,
    previous_context: str,
    requirements: str,
    generation_notes: list[str],
) -> str:
    outline_context = compact_outline_context(outline)
    min_words = min_content_length(target_words)
    current = content.strip()
    for attempt in range(1, 4):
        current_len = content_length(current)
        if current_len >= min_words:
            return current
        missing = min_words - current_len
        user = CHAPTER_CONTINUE_USER.format(
            outline_context=outline_context,
            chapter_plan_json=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
            written_tail=current[-1600:] if current else (previous_context or "无"),
            current_words=current_len,
            target_words=target_words,
            missing_words=missing,
        )
        addition = _clean_prose(chat_text(CHAPTER_CONTINUE_SYSTEM, user))
        if not addition:
            generation_notes.append(f"补写 {attempt} 未返回有效正文。")
            break
        before = content_length(current)
        current = (current + "\n\n" + addition).strip()
        after = content_length(current)
        generation_notes.append(f"补写 {attempt} 增加：{after - before}，当前：{after}。")
        if after <= before + 50:
            break
    return current


def expand_chapter_to_target(outline: NovelOutline, chapter: ChapterDraft, target_words: int) -> ChapterDraft:
    min_words = min_content_length(target_words)
    user = CHAPTER_EXPAND_USER.format(
        outline_json=outline.model_dump_json(indent=2),
        chapter_json=chapter.model_dump_json(indent=2),
        current_words=content_length(chapter.content),
        target_words=int(target_words),
        min_target_words=min_words,
    )
    data = chat_json(CHAPTER_EXPAND_SYSTEM, user)
    data.setdefault("outline_title", chapter.outline_title or outline_title(outline))
    data.setdefault("chapter_no", chapter.chapter_no)
    data.setdefault("title", chapter.title)
    return ChapterDraft(**data)


def ensure_chapter_length(outline: NovelOutline, chapter: ChapterDraft, target_words: int) -> ChapterDraft:
    chapter.target_words = int(target_words)
    chapter.actual_length = content_length(chapter.content)
    # For short test generations, do not force a second model call.
    if int(target_words) < 1200:
        return chapter
    if content_length(chapter.content) >= min_content_length(target_words):
        return chapter
    expanded = expand_chapter_to_target(outline, chapter, int(target_words))
    # If expansion still fails, return the longer version rather than looping.
    if content_length(expanded.content) > content_length(chapter.content):
        expanded.target_words = int(target_words)
        expanded.actual_length = content_length(expanded.content)
        return expanded
    return chapter


def generate_chapter_series(
    outline: NovelOutline,
    start_chapter: int = 1,
    chapter_count: int = 1,
    target_words: int = 2500,
    previous_context: str = "",
    requirements: str = "",
) -> list[ChapterDraft]:
    """Generate a chosen number of consecutive chapters.

    This intentionally requires an explicit ``chapter_count`` so the app never
    expands a whole novel by accident.  Each generated chapter feeds a compact
    continuity context into the next chapter.
    """
    count = max(1, min(int(chapter_count), 50))
    chapters: list[ChapterDraft] = []
    context = previous_context.strip()
    for offset in range(count):
        chapter_no = int(start_chapter) + offset
        chapter = generate_chapter(
            outline=outline,
            chapter_no=chapter_no,
            target_words=target_words,
            previous_context=context,
            requirements=requirements,
        )
        chapters.append(chapter)
        context = "\n".join(
            [
                context[-1500:] if context else "",
                f"刚生成第 {chapter.chapter_no} 章《{chapter.title}》。",
                f"本章目标：{chapter.chapter_goal}",
                f"核心冲突：{chapter.conflict}",
                f"章末钩子：{chapter.ending_hook}",
                f"下一章种子：{chapter.next_chapter_seed}",
            ]
        ).strip()
    return chapters


def polish_chapter(
    outline: NovelOutline,
    chapter: ChapterDraft,
    review: ChapterReview,
) -> ChapterDraft:
    require_llm_configured()
    user = CHAPTER_POLISH_USER.format(
        outline_json=outline.model_dump_json(indent=2),
        chapter_json=chapter.model_dump_json(indent=2),
        review_json=review.model_dump_json(indent=2),
    )
    data = chat_json(CHAPTER_POLISH_SYSTEM, user)
    data.setdefault("outline_title", chapter.outline_title or outline_title(outline))
    data.setdefault("chapter_no", chapter.chapter_no)
    data.setdefault("title", chapter.title)
    return ChapterDraft(**data)


def load_chapter_from_path(path: Path) -> ChapterDraft:
    return ChapterDraft(**json.loads(path.read_text(encoding="utf-8")))


def list_chapter_files() -> list[Path]:
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(CHAPTER_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def chapter_to_markdown(chapter: ChapterDraft) -> str:
    lines = [
        f"# 第 {chapter.chapter_no} 章：{chapter.title}",
        "",
        f"- 大纲：{chapter.outline_title}",
        f"- 视角：{chapter.pov}",
        f"- 本章目标：{chapter.chapter_goal}",
        f"- 核心冲突：{chapter.conflict}",
        "",
        "## 正文",
        "",
        chapter.content.strip(),
        "",
        "## 章末钩子",
        "",
        chapter.ending_hook.strip(),
    ]
    if chapter.continuity_notes:
        lines.extend(["", "## 后续衔接", ""])
        lines.extend(f"- {x}" for x in chapter.continuity_notes)
    if chapter.originality_notes:
        lines.extend(["", "## 原创避撞说明", ""])
        lines.extend(f"- {x}" for x in chapter.originality_notes)
    if chapter.next_chapter_seed:
        lines.extend(["", "## 下一章种子", "", chapter.next_chapter_seed.strip()])
    return "\n".join(lines).strip() + "\n"


def save_chapter_files(chapter: ChapterDraft) -> tuple[Path, Path]:
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outline_safe = _safe_name(chapter.outline_title, "outline")
    title_safe = _safe_name(chapter.title, f"chapter_{chapter.chapter_no}")
    base = f"{stamp}_{outline_safe}_第{chapter.chapter_no:03d}章_{title_safe}"
    json_path = CHAPTER_DIR / f"{base}.json"
    md_path = CHAPTER_DIR / f"{base}.md"
    json_path.write_text(json.dumps(chapter.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(chapter_to_markdown(chapter), encoding="utf-8")
    return json_path, md_path
