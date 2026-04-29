from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import CHAPTER_QUALITY_DIR
from ..schemas import ChapterDraft, NovelOutline
from .chapter_generator import chapter_plan_from_outline, content_length, outline_title
from .chapter_reviewer import chinese_terms


TEMPLATE_PATTERNS: list[tuple[str, str, str]] = [
    ("模型说明口吻", r"作为AI|根据你的要求|以下是|我将为你|本章主要|这一章通过|综上所述", "删除元叙事说明，直接进入小说正文。"),
    ("高频模板套话", r"全场死寂|空气仿佛凝固|命运齿轮|他不知道的是|所有人都愣住|震惊(?:了)?所有人|下一秒，全场|这一刻，(?:他|她|所有人)", "换成具体动作、物件变化、对白停顿或旁人反应。"),
    ("抽象爽点标签", r"爽点拉满|压迫感(?:十足|拉满)|情绪价值|节奏拉满|反转很炸|代入感(?:十足|拉满)", "不要用创作术语评价正文，把爽点写成可见事件。"),
    ("解释腔过重", r"这意味着|换句话说|也就是说|从某种意义上|显而易见|毫无疑问", "把解释改成角色判断、误判、争执或行动。"),
]

ABSTRACT_EMOTIONS = ("震惊", "愤怒", "害怕", "紧张", "激动", "复杂", "崩溃", "恐惧", "绝望", "惊讶")
DETAIL_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9]{0,10}(?:记录|钥匙|照片|短信|账单|车票|编号|监控|名单|签名|纹身|旧伤|录音|合同|便签|地址|药瓶|戒指|发票|档案|门禁卡|血迹|摄像头|纸条)[\u4e00-\u9fffA-Za-z0-9]{0,10}"
)
REVERSAL_SIGNALS = r"却|但|然而|反而|原来|其实|真正|不是|竟然|偏偏|问题是|没想到|反咬|陷阱|背叛|误判"
STAKE_SIGNALS = r"代价|威胁|暴露|失去|倒计时|背叛|陷阱|反咬|债|死|毁|封杀|举报|抓走|失踪|交换"
HARD_TWIST_PATTERNS = r"毫无征兆|突然出现一个陌生人|原来一切都是梦|其实他一直知道|没任何理由|凭空出现"


class AIVoiceReport(BaseModel):
    score: int = 100
    verdict: str = "自然"
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ForeshadowEntry(BaseModel):
    clue: str
    chapter_no: int
    category: str = "伏笔"
    reader_visibility: str = "可见"
    evidence: str = ""
    planned_payoff: str = ""
    status: str = "待回收"
    suggestion: str = ""


class ReversalReview(BaseModel):
    score: int = 100
    verdict: str = "有迹可循"
    twist: str = ""
    hook_type: str = ""
    foreshadowing: str = ""
    reversal_logic: str = ""
    checks: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ChapterQualityReport(BaseModel):
    id: str
    outline_title: str = ""
    chapter_no: int = 1
    chapter_title: str = ""
    overall_score: int = 0
    summary: str = ""
    ai_voice: AIVoiceReport
    foreshadow_ledger: list[ForeshadowEntry] = Field(default_factory=list)
    reversal_review: ReversalReview
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _safe_name(value: str, fallback: str = "quality") -> str:
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_.-]+", "_", value or fallback).strip("_")
    return safe[:70] or fallback


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{k}:{_text(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_text(x) for x in value)
    return str(value)


def _paragraphs(content: str) -> list[str]:
    parts = [x.strip() for x in re.split(r"\n+", content or "") if x.strip()]
    if len(parts) <= 1:
        parts = [x.strip() for x in re.split(r"(?<=[。！？!?])", content or "") if x.strip()]
    return parts


def _excerpt(text: str, start: int, end: int, *, pad: int = 34) -> str:
    left = max(0, start - pad)
    right = min(len(text), end + pad)
    return ("…" if left else "") + text[left:right].replace("\n", " ") + ("…" if right < len(text) else "")


def _check(name: str, ok: bool, penalty: int, message: str, suggestion: str, level: str = "warning") -> dict[str, Any]:
    return {
        "项目": name,
        "通过": bool(ok),
        "扣分": 0 if ok else int(penalty),
        "级别": "通过" if ok else level,
        "说明": message,
        "建议": suggestion,
    }


def review_ai_voice(chapter: ChapterDraft) -> AIVoiceReport:
    content = chapter.content or ""
    length = max(1, content_length(content))
    paragraphs = _paragraphs(content)
    issues: list[dict[str, Any]] = []
    suggestions: list[str] = []
    penalty = 0

    for label, pattern, suggestion in TEMPLATE_PATTERNS:
        matches = list(re.finditer(pattern, content))
        if not matches:
            continue
        hit_penalty = min(24, 6 * len(matches))
        penalty += hit_penalty
        suggestions.append(suggestion)
        for match in matches[:6]:
            issues.append(
                {
                    "类型": label,
                    "严重度": "高" if label in {"模型说明口吻", "高频模板套话"} else "中",
                    "原文": _excerpt(content, match.start(), match.end()),
                    "建议": suggestion,
                }
            )

    abstract_count = sum(content.count(word) for word in ABSTRACT_EMOTIONS)
    detail_count = len(DETAIL_PATTERN.findall(content))
    if abstract_count >= 8 and detail_count < max(2, abstract_count // 4):
        penalty += min(14, abstract_count)
        issues.append(
            {
                "类型": "抽象情绪偏多",
                "严重度": "中",
                "原文": f"抽象情绪词 {abstract_count} 次，具体物件线索 {detail_count} 个。",
                "建议": "把震惊、愤怒、紧张改成动作、手势、物件变化、对白停顿或场景压力。",
            }
        )
        suggestions.append("把抽象情绪词改成可见细节。")

    long_explain = [p for p in paragraphs if content_length(p) >= 260 and ("“" not in p and '"' not in p)]
    if len(long_explain) >= 2:
        penalty += min(18, 6 * len(long_explain))
        issues.append(
            {
                "类型": "长段解释",
                "严重度": "中",
                "原文": long_explain[0][:140] + ("…" if len(long_explain[0]) > 140 else ""),
                "建议": "拆成动作、对白、选择或冲突推进，避免连续说明书式叙述。",
            }
        )
        suggestions.append("把长段解释拆成场景动作和对白。")

    dialogue_count = content.count("“") + content.count('"') // 2
    dialogue_ratio = dialogue_count / max(1, len(paragraphs))
    if length >= 1200 and dialogue_ratio < 0.35:
        penalty += 10
        issues.append(
            {
                "类型": "对白不足",
                "严重度": "低",
                "原文": f"自然段 {len(paragraphs)}，对白信号 {dialogue_count}。",
                "建议": "增加试探、质问、隐瞒、误解或反击型对白，让人物声音区别于旁白。",
            }
        )
        suggestions.append("增加有目的的对白，减少单一旁白推进。")

    sentence_like = re.split(r"[。！？!?；;]\s*", content)
    repeated_starts: dict[str, int] = {}
    for sent in sentence_like:
        clean = re.sub(r"\s+", "", sent)
        if len(clean) >= 6:
            repeated_starts[clean[:3]] = repeated_starts.get(clean[:3], 0) + 1
    repeated = {k: v for k, v in repeated_starts.items() if v >= 5}
    if repeated:
        penalty += min(10, len(repeated) * 3)
        issues.append(
            {
                "类型": "句式重复",
                "严重度": "低",
                "原文": "、".join(f"{k}…×{v}" for k, v in list(repeated.items())[:5]),
                "建议": "调整句长和句首结构，加入短句、停顿、动作插入和人物口吻。",
            }
        )
        suggestions.append("打散重复句式，加入人物化表达。")

    score = max(0, 100 - penalty)
    verdict = "自然" if score >= 86 else "轻微AI味" if score >= 70 else "AI味偏重" if score >= 50 else "需要重写"
    metrics = [
        {"指标": "正文长度", "值": length, "说明": "非空白字符近似字数"},
        {"指标": "自然段", "值": len(paragraphs), "说明": "段落越清晰越利于编辑"},
        {"指标": "对白信号", "值": dialogue_count, "说明": "中文引号和英文引号"},
        {"指标": "模板/说明问题", "值": len([x for x in issues if x["类型"] in {"模型说明口吻", "高频模板套话", "抽象爽点标签", "解释腔过重"}]), "说明": "越少越好"},
        {"指标": "具体物件线索", "值": detail_count, "说明": "账单、钥匙、记录、监控等"},
    ]
    return AIVoiceReport(score=score, verdict=verdict, metrics=metrics, issues=issues, suggestions=list(dict.fromkeys(suggestions))[:8])


def build_foreshadow_ledger(outline: NovelOutline, chapter: ChapterDraft) -> list[ForeshadowEntry]:
    plan = chapter_plan_from_outline(outline, int(chapter.chapter_no))
    content = chapter.content or ""
    compact = re.sub(r"\s+", "", content)
    payoff = _text(plan.get("ending_hook") or chapter.next_chapter_seed or "后续 3-8 章回收")
    entries: list[ForeshadowEntry] = []
    seen: set[str] = set()

    def add(clue: str, category: str, planned_payoff: str = "", suggestion: str = "") -> None:
        clue = re.sub(r"\s+", " ", str(clue or "")).strip()
        if not clue or clue in seen:
            return
        seen.add(clue)
        terms = chinese_terms(clue, limit=8)
        evidence = next((term for term in terms if term and term in compact), "")
        entries.append(
            ForeshadowEntry(
                clue=clue[:120],
                chapter_no=int(chapter.chapter_no),
                category=category,
                reader_visibility="已落地" if evidence or clue in content else "计划中未落地",
                evidence=evidence or (clue[:40] if clue in content else ""),
                planned_payoff=(planned_payoff or payoff)[:160],
                status="待回收",
                suggestion=suggestion or "后续章节回收时要改变读者对这条线索的理解。",
            )
        )

    add(_text(plan.get("foreshadowing")), "计划伏笔", _text(plan.get("reversal_logic")), "在正文中用低调物件、对白漏洞或异常动作落地。")
    add(_text(plan.get("ending_hook") or chapter.ending_hook), "章末钩子", "下一章或本卷阶段回收", "下一章开篇优先兑现或升级，避免只吊胃口。")
    add(chapter.next_chapter_seed, "下章种子", "下一章开篇承接", "作为下一章开篇冲突或误判入口。")
    for note in chapter.continuity_notes[:6]:
        add(note, "连续性伏笔", "后续保持设定一致", "生成后续章节时必须带入。")

    for match in DETAIL_PATTERN.finditer(content):
        clue = match.group(0).strip("，。！？；：“”\"'（）()、 ")
        if 2 <= len(clue) <= 30:
            add(clue, "物件/证据线索", payoff, "给这件物品或证据安排明确回收点。")
        if len(entries) >= 18:
            break

    return entries[:20]


def review_reversal(outline: NovelOutline, chapter: ChapterDraft, ledger: list[ForeshadowEntry] | None = None) -> ReversalReview:
    plan = chapter_plan_from_outline(outline, int(chapter.chapter_no))
    content = chapter.content or ""
    compact = re.sub(r"\s+", "", content)
    twist = _text(plan.get("twist") or chapter.conflict)
    hook_type = _text(plan.get("hook_type"))
    foreshadowing = _text(plan.get("foreshadowing"))
    reversal_logic = _text(plan.get("reversal_logic"))
    ledger = ledger or []

    twist_terms = chinese_terms(twist, limit=12)
    clue_terms = chinese_terms(foreshadowing, limit=12)
    logic_terms = chinese_terms(reversal_logic, limit=12)
    twist_hits = [t for t in twist_terms if t in compact]
    clue_hits = [t for t in clue_terms if t in compact]
    logic_hits = [t for t in logic_terms if t in compact]
    signal_count = len(re.findall(REVERSAL_SIGNALS, content))
    stake_count = len(re.findall(STAKE_SIGNALS, content))
    landed_ledger = [x for x in ledger if x.reader_visibility == "已落地"]
    hard_hits = re.findall(HARD_TWIST_PATTERNS, content)

    checks = [
        _check("反转目标可见", bool(twist_hits) or signal_count >= 4, 22, f"反转关键词命中 {len(twist_hits)} 个，反转信号 {signal_count}。", "把 twist 写成可见局势变化，而不是只在计划里存在。", "error"),
        _check("提前伏笔可见", bool(clue_hits) or bool(landed_ledger), 24, f"伏笔命中 {len(clue_hits)} 个，已落地台账 {len(landed_ledger)} 条。", "在反转前补一个不起眼线索：物件、对白漏洞、规则例外或小动作。", "error"),
        _check("反转因果合理", bool(logic_hits) or bool(reversal_logic and (twist_hits or clue_hits or landed_ledger)), 18, f"反转逻辑关键词命中 {len(logic_hits)} 个。", "补清楚反转来自人物利益、能力代价、前文证据或规则限制。"),
        _check("局势被改变", stake_count >= 4, 14, f"代价/风险信号 {stake_count}。", "反转后要让优势变代价、救援变陷阱、证据反咬或关系破裂。"),
        _check("无硬拐信号", not hard_hits, 16, "未发现明显硬拐句。" if not hard_hits else "发现：" + "、".join(hard_hits[:5]), "删除无征兆反转，改为前文可回看的证据重解释。", "error"),
    ]
    score = max(0, 100 - sum(int(c.get("扣分", 0)) for c in checks))
    error_count = sum(1 for c in checks if not c.get("通过") and c.get("级别") == "error")
    verdict = "有迹可循" if score >= 84 and error_count == 0 else "可小修" if score >= 68 and error_count <= 1 else "反转偏硬" if score >= 50 else "需要重构"
    suggestions = [c["建议"] for c in checks if not c.get("通过") and c.get("建议")]
    return ReversalReview(
        score=score,
        verdict=verdict,
        twist=twist,
        hook_type=hook_type,
        foreshadowing=foreshadowing,
        reversal_logic=reversal_logic,
        checks=checks,
        suggestions=suggestions[:8],
    )


def inspect_chapter_quality(outline: NovelOutline, chapter: ChapterDraft) -> ChapterQualityReport:
    ai_voice = review_ai_voice(chapter)
    ledger = build_foreshadow_ledger(outline, chapter)
    reversal = review_reversal(outline, chapter, ledger)
    ledger_score = 100 if any(x.reader_visibility == "已落地" for x in ledger) else 70 if ledger else 55
    overall = round(ai_voice.score * 0.36 + reversal.score * 0.44 + ledger_score * 0.20)
    summary = f"AI味：{ai_voice.verdict} {ai_voice.score}/100；反转：{reversal.verdict} {reversal.score}/100；伏笔台账 {len(ledger)} 条。"
    return ChapterQualityReport(
        id=f"quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}_ch{int(chapter.chapter_no):03d}",
        outline_title=outline_title(outline),
        chapter_no=int(chapter.chapter_no),
        chapter_title=chapter.title,
        overall_score=int(overall),
        summary=summary,
        ai_voice=ai_voice,
        foreshadow_ledger=ledger,
        reversal_review=reversal,
    )


def quality_to_markdown(report: ChapterQualityReport) -> str:
    ai_issues = "\n".join(f"- ⚠️ {x.get('类型')}：{x.get('原文')}｜建议：{x.get('建议')}" for x in report.ai_voice.issues) or "- 暂无明显 AI 味问题。"
    ai_suggestions = "\n".join(f"- {x}" for x in report.ai_voice.suggestions) or "- 暂无。"
    ledger = "\n".join(
        f"- **{x.category}**：{x.clue}｜可见性：{x.reader_visibility}｜证据：{x.evidence or '待补'}｜回收：{x.planned_payoff}"
        for x in report.foreshadow_ledger
    ) or "- 暂无伏笔条目。"
    reversal_checks = "\n".join(
        f"- {'✅' if c.get('通过') else '⚠️'} {c.get('项目')}：{c.get('说明')} {('建议：' + c.get('建议')) if c.get('建议') and not c.get('通过') else ''}"
        for c in report.reversal_review.checks
    )
    reversal_suggestions = "\n".join(f"- {x}" for x in report.reversal_review.suggestions) or "- 暂无。"
    return f"""# 章节质检报告 · 第 {report.chapter_no} 章《{report.chapter_title}》

- 大纲：{report.outline_title}
- 综合分：{report.overall_score}
- 摘要：{report.summary}
- 时间：{report.created_at}

## AI味检测

- 结论：{report.ai_voice.verdict}
- 分数：{report.ai_voice.score}

{ai_issues}

### 去AI味建议

{ai_suggestions}

## 伏笔台账

{ledger}

## 反转审查

- 结论：{report.reversal_review.verdict}
- 分数：{report.reversal_review.score}
- 反转：{report.reversal_review.twist or '未标注'}
- 钩子类型：{report.reversal_review.hook_type or '未标注'}
- 伏笔：{report.reversal_review.foreshadowing or '未标注'}
- 反转逻辑：{report.reversal_review.reversal_logic or '未标注'}

{reversal_checks}

### 反转修改建议

{reversal_suggestions}
"""


def save_quality_report(report: ChapterQualityReport) -> tuple[Path, Path]:
    CHAPTER_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{report.id}_{_safe_name(report.chapter_title)}"
    json_path = CHAPTER_QUALITY_DIR / f"{base}.json"
    md_path = CHAPTER_QUALITY_DIR / f"{base}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(quality_to_markdown(report), encoding="utf-8")
    return json_path, md_path


def list_quality_report_files() -> list[Path]:
    CHAPTER_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(CHAPTER_QUALITY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
