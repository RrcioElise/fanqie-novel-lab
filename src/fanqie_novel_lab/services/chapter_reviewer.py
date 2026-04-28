from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import CHAPTER_AUDIT_DIR
from ..schemas import ChapterDraft, NovelOutline
from .chapter_generator import chapter_plan_from_outline, content_length, outline_title

STOPWORDS = {
    "一个", "一种", "这个", "那个", "自己", "他们", "她们", "我们", "你们", "已经", "开始", "进行", "因为", "所以", "但是", "然后",
    "主角", "本章", "目标", "冲突", "反转", "钩子", "阶段", "推进", "出现", "发现", "知道", "没有", "不是", "成为",
}
AI_TONE_PATTERNS = [r"作为AI", r"根据你的要求", r"以下是", r"我将为你", r"本章主要", r"这一章通过"]


class ChapterAudit(BaseModel):
    id: str
    outline_title: str = ""
    chapter_no: int = 1
    chapter_title: str = ""
    score: int = 0
    verdict: str = "待审核"
    summary: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    missing_plan_keywords: list[str] = Field(default_factory=list)
    matched_plan_keywords: list[str] = Field(default_factory=list)
    revision_advice: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _safe_name(value: str, fallback: str = "chapter_audit") -> str:
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_.-]+", "_", value or fallback).strip("_")
    return safe[:70] or fallback


def _text_from_any(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_text_from_any(x) for x in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}:{_text_from_any(v)}" for k, v in value.items())
    return str(value)


def chinese_terms(text: str, *, min_len: int = 2, max_len: int = 6, limit: int = 40) -> list[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", text or "")
    raw: list[str] = []
    for part in text.split():
        if re.fullmatch(r"[A-Za-z0-9]{2,}", part):
            raw.append(part.lower())
            continue
        chars = "".join(re.findall(r"[\u4e00-\u9fff]", part))
        if len(chars) < min_len:
            continue
        for size in range(min(max_len, len(chars)), min_len - 1, -1):
            for i in range(0, len(chars) - size + 1):
                token = chars[i : i + size]
                if token not in STOPWORDS and not any(sw in token and len(token) <= len(sw) + 1 for sw in STOPWORDS):
                    raw.append(token)
    seen: dict[str, int] = {}
    for token in raw:
        seen[token] = seen.get(token, 0) + 1
    return [x for x, _ in sorted(seen.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[:limit]]


def _keyword_match(expected_text: str, content: str, *, limit: int = 24) -> tuple[list[str], list[str]]:
    terms = chinese_terms(expected_text, limit=limit)
    content_compact = re.sub(r"\s+", "", content or "")
    matched = [t for t in terms if t in content_compact]
    missing = [t for t in terms if t not in content_compact]
    return matched, missing


def _check(name: str, ok: bool, score_delta: int, message: str, advice: str = "", level: str = "warning") -> dict[str, Any]:
    return {
        "项目": name,
        "通过": bool(ok),
        "扣分": 0 if ok else int(score_delta),
        "级别": "通过" if ok else level,
        "说明": message,
        "建议": advice,
    }


def audit_chapter_against_outline(
    outline: NovelOutline,
    chapter: ChapterDraft,
    *,
    target_words: int | None = None,
) -> ChapterAudit:
    plan = chapter_plan_from_outline(outline, int(chapter.chapter_no))
    content = chapter.content or ""
    compact = re.sub(r"\s+", "", content)
    length = content_length(content)
    expected_text = "\n".join(
        _text_from_any(plan.get(k, "")) for k in ["title", "goal", "conflict", "twist", "ending_hook"]
    )
    matched, missing = _keyword_match(expected_text, content)
    checks: list[dict[str, Any]] = []

    plan_keyword_ratio = len(matched) / max(1, len(matched) + len(missing))
    checks.append(
        _check(
            "大纲计划贴合",
            plan_keyword_ratio >= 0.28 or len(matched) >= 5,
            24,
            f"计划关键词命中 {len(matched)} 个，缺失 {len(missing)} 个。",
            "补回本章目标、冲突、反转或章末钩子中的关键事件；不要只写氛围和旁支。",
            "error",
        )
    )

    target = int(target_words or chapter.target_words or 0)
    if target > 0:
        checks.append(
            _check(
                "字数目标",
                int(target * 0.85) <= length <= int(target * 1.25),
                8,
                f"当前 {length} 字，目标 {target} 字。",
                "差距过大时先扩写/压缩，再进入发布包。",
            )
        )
    else:
        checks.append(_check("字数记录", length >= 800, 5, f"当前 {length} 字。", "建议至少达到平台单章基础长度。"))

    goal_text = _text_from_any(plan.get("goal", ""))
    goal_matched, goal_missing = _keyword_match(goal_text, content, limit=10)
    checks.append(
        _check(
            "本章目标兑现",
            bool(goal_matched) or not goal_text.strip(),
            14,
            f"目标命中：{'、'.join(goal_matched[:6]) or '无明显命中'}。",
            "把本章目标写成主角可见行动和结果，避免只做铺垫。",
            "error",
        )
    )

    conflict_text = _text_from_any(plan.get("conflict", ""))
    conflict_matched, _ = _keyword_match(conflict_text, content, limit=10)
    conflict_signals = len(re.findall(r"不|却|但|逼|怒|吼|威胁|质问|反击|危险|死|抢|拦|赔|债|秘密", content))
    checks.append(
        _check(
            "核心冲突存在",
            bool(conflict_matched) or conflict_signals >= 8,
            14,
            f"冲突词命中：{'、'.join(conflict_matched[:6]) or '弱'}；冲突信号 {conflict_signals}。",
            "增加外部阻力、代价、质问、误判或反击，不要写成平铺直叙。",
            "error",
        )
    )

    hook_text = _text_from_any(plan.get("ending_hook", ""))
    tail = compact[-900:]
    hook_matched, _ = _keyword_match(hook_text, tail, limit=10)
    tail_has_hook = bool(re.search(r"？|!|！|却|突然|下一秒|门外|手机|消息|秘密|真相|危险|死定|不见了|响了", tail))
    checks.append(
        _check(
            "章末钩子",
            bool(hook_matched) or tail_has_hook,
            12,
            f"尾段钩子命中：{'、'.join(hook_matched[:6]) or '未明显命中'}。",
            "最后 300-800 字要落到下一章必须解决的问题。",
        )
    )

    protagonist_text = _text_from_any(outline.protagonist)
    character_text = protagonist_text + "\n" + _text_from_any(outline.key_characters[:5])
    character_terms = chinese_terms(character_text, limit=18)
    character_hits = [t for t in character_terms if t in compact]
    checks.append(
        _check(
            "人物/设定连续性",
            len(character_hits) >= min(3, max(1, len(character_terms) // 4)) or not character_terms,
            10,
            f"人物设定命中：{'、'.join(character_hits[:8]) or '不足'}。",
            "检查主角身份、能力代价、关键关系是否和大纲一致。",
        )
    )

    rule_text = _text_from_any(outline.power_system_or_hook_rules[:6])
    rule_terms = chinese_terms(rule_text, limit=14)
    rule_hits = [t for t in rule_terms if t in compact]
    checks.append(
        _check(
            "核心规则可见",
            len(rule_hits) >= 1 or not rule_terms,
            8,
            f"规则命中：{'、'.join(rule_hits[:6]) or '未明显出现'}。",
            "如果本章涉及金手指，必须体现边界、代价或后果。",
        )
    )

    dialogue_count = content.count("“") + content.count('"') // 2
    paragraph_count = len([x for x in content.splitlines() if x.strip()])
    checks.append(
        _check(
            "正文可读性",
            paragraph_count >= 8 and dialogue_count >= 4,
            7,
            f"自然段 {paragraph_count}，对白信号 {dialogue_count}。",
            "增加场景、动作和对白，减少说明书式叙述。",
        )
    )

    ai_hit = [p for p in AI_TONE_PATTERNS if re.search(p, content)]
    checks.append(
        _check(
            "无出戏说明",
            not ai_hit,
            8,
            f"{'未发现模型说明口吻' if not ai_hit else '发现：' + '、'.join(ai_hit)}。",
            "删除“以下是/本章主要/根据要求”等元叙事。",
        )
    )

    score = max(0, 100 - sum(int(c.get("扣分", 0)) for c in checks))
    error_count = sum(1 for c in checks if not c.get("通过") and c.get("级别") == "error")
    if score >= 85 and error_count == 0:
        verdict = "通过"
    elif score >= 68 and error_count <= 1:
        verdict = "需小修"
    elif score >= 50:
        verdict = "需重修"
    else:
        verdict = "疑似跑题"

    advice = [c["建议"] for c in checks if not c.get("通过") and c.get("建议")]
    summary = f"{verdict}：本章与计划关键词命中率 {plan_keyword_ratio:.0%}，总分 {score}。"
    return ChapterAudit(
        id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_ch{int(chapter.chapter_no):03d}",
        outline_title=outline_title(outline),
        chapter_no=int(chapter.chapter_no),
        chapter_title=chapter.title,
        score=score,
        verdict=verdict,
        summary=summary,
        plan=plan,
        checks=checks,
        missing_plan_keywords=missing[:30],
        matched_plan_keywords=matched[:30],
        revision_advice=advice[:10],
    )


def audit_to_markdown(audit: ChapterAudit) -> str:
    checks = "\n".join(
        f"- {'✅' if c.get('通过') else '⚠️'} {c.get('项目')}（{c.get('级别')}）：{c.get('说明')} {('建议：' + c.get('建议')) if c.get('建议') and not c.get('通过') else ''}"
        for c in audit.checks
    )
    advice = "\n".join(f"- {x}" for x in audit.revision_advice) or "- 暂无。"
    plan = json.dumps(audit.plan, ensure_ascii=False, indent=2)
    return f"""# 章节审核报告 · 第 {audit.chapter_no} 章《{audit.chapter_title}》

- 大纲：{audit.outline_title}
- 结论：{audit.verdict}
- 分数：{audit.score}
- 摘要：{audit.summary}
- 时间：{audit.created_at}

## 检查项

{checks}

## 命中关键词

{', '.join(audit.matched_plan_keywords) or '无'}

## 缺失关键词

{', '.join(audit.missing_plan_keywords) or '无'}

## 修改建议

{advice}

## 对照章节计划

```json
{plan}
```
"""


def save_chapter_audit(audit: ChapterAudit) -> tuple[Path, Path]:
    CHAPTER_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{audit.id}_{_safe_name(audit.chapter_title)}"
    json_path = CHAPTER_AUDIT_DIR / f"{base}.json"
    md_path = CHAPTER_AUDIT_DIR / f"{base}.md"
    json_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(audit_to_markdown(audit), encoding="utf-8")
    return json_path, md_path


def list_chapter_audit_files() -> list[Path]:
    CHAPTER_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(CHAPTER_AUDIT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
