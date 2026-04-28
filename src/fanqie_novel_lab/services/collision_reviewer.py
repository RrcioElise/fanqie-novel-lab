from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from rapidfuzz import fuzz

from ..config import REVIEW_DIR
from ..schemas import BookMeta, NovelOutline

STOPWORDS = set(
    "的了一是在和与及或而也就都很被把给让对为从到于中里上下一二三四五六七八九十"
    "主角自己一个这个那个他们我们你们没有因为所以但是如果然后开始突然发现获得成为进行"
)

HOOK_WORDS = [
    "系统", "重生", "穿越", "直播", "神豪", "签到", "记忆", "隐藏信息", "异能", "金手指", "逆袭",
    "都市", "脑洞", "算命", "钓鱼", "水库", "县城", "消费", "军旅", "娱乐圈", "综艺", "马甲",
    "学神", "高考", "源点", "粒子", "续命", "塔罗", "民政局", "摆摊", "基建", "种田", "爽文",
    "单女主", "直播曝光", "隐藏身份", "反杀", "打脸", "富豪", "商业", "乡村", "官场", "悬疑",
]


def _safe_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _model_like_to_dict(value: Any) -> dict | None:
    """Return a dict for pydantic/model-like objects.

    Streamlit can keep objects created before a module hot-reload in
    ``st.session_state``.  Those objects still print as ``NovelOutline``, but
    ``isinstance(value, NovelOutline)`` may fail because the class object was
    reloaded.  Use duck-typing so the reviewer accepts current objects, stale
    Streamlit objects, uploaded JSON dicts, and plain text.
    """
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else None
        except Exception:
            pass
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            dumped = dict_method()
            return dumped if isinstance(dumped, dict) else None
        except Exception:
            pass
    if value.__class__.__name__ == "NovelOutline" and hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return None


def _extend_parts(parts: list[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _extend_parts(parts, item)
        return
    text = _safe_json_text(value).strip()
    if text:
        parts.append(text)


def outline_title_candidates(outline: Any) -> list[str]:
    data = _model_like_to_dict(outline)
    if data is not None:
        candidates = data.get("title_candidates") or []
    else:
        candidates = getattr(outline, "title_candidates", []) or []
    if isinstance(candidates, str):
        return [candidates]
    return [str(x) for x in candidates if x]


def outline_to_text(outline: NovelOutline | str | dict | Any) -> str:
    if isinstance(outline, str):
        return outline

    data = _model_like_to_dict(outline)
    if data is not None:
        parts: list[str] = []
        for key in [
            "title_candidates",
            "one_line_pitch",
            "selling_points",
            "genre_positioning",
            "world_setting",
            "protagonist",
            "key_characters",
            "antagonist_design",
            "power_system_or_hook_rules",
            "volume_plan",
            "first_10_chapters",
            "long_arc",
            "recurring_hooks",
        ]:
            _extend_parts(parts, data.get(key))
        return "\n".join(parts) if parts else json.dumps(data, ensure_ascii=False, indent=2, default=str)

    return _safe_json_text(outline)


def book_to_text(book: BookMeta) -> str:
    return "\n".join(
        [
            book.title,
            book.author,
            book.category,
            book.rank_name,
            book.description,
            " ".join(book.tags),
        ]
    )


def chinese_tokens(text: Any, min_len: int = 2, max_len: int = 8) -> list[str]:
    if not isinstance(text, str):
        text = outline_to_text(text)
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", text or "")
    tokens: list[str] = []
    for seg in text.split():
        if not seg:
            continue
        # English/digit token
        if re.fullmatch(r"[A-Za-z0-9]+", seg):
            if len(seg) >= min_len:
                tokens.append(seg.lower())
            continue
        # Chinese n-grams, better than no tokenizer for short webnovel hooks.
        chars = [c for c in seg if c not in STOPWORDS]
        compact = "".join(chars)
        for n in range(min_len, min(max_len, len(compact)) + 1):
            for i in range(0, len(compact) - n + 1):
                tok = compact[i : i + n]
                if tok and tok not in STOPWORDS:
                    tokens.append(tok)
    return tokens


def top_keywords(text: Any, limit: int = 30) -> list[str]:
    if not isinstance(text, str):
        text = outline_to_text(text)
    counter = Counter(chinese_tokens(text, min_len=2, max_len=5))
    # Boost known hook words if present.
    for word in HOOK_WORDS:
        if word in text:
            counter[word] += 8
    return [w for w, _ in counter.most_common(limit)]


def ngrams(text: Any, n: int = 3) -> set[str]:
    if not isinstance(text, str):
        text = outline_to_text(text)
    compact = re.sub(r"\s+", "", re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", text or "").lower())
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def overlap_items(a: list[str], b: list[str], limit: int = 12) -> list[str]:
    sb = set(b)
    seen: set[str] = set()
    out: list[str] = []
    for item in a:
        if item in sb and item not in seen:
            seen.add(item)
            out.append(item)
        if len(out) >= limit:
            break
    return out


def risk_level(score: float) -> str:
    if score >= 78:
        return "高风险"
    if score >= 58:
        return "中风险"
    if score >= 38:
        return "低风险"
    return "参考"


def advice_for_finding(level: str, overlaps: list[str]) -> str:
    if level == "高风险":
        return "建议重做核心钩子、主角职业/压力源、金手指代价和前三章事件，避免只改名换皮。"
    if level == "中风险":
        return "建议保留题材方向，但改动关键爽点组合、能力规则、反派结构和阶段目标。"
    if overlaps:
        return "可作为题材趋势参考，但不要复用相同钩子排列；强化原创变量。"
    return "相似度较低，继续保持原创设定。"


def compare_outline_to_books(
    outline: NovelOutline | str | dict,
    books: list[BookMeta],
    min_score: float = 30,
    top_n: int = 30,
) -> list[dict]:
    target_text = outline_to_text(outline)
    target_keywords = top_keywords(target_text, limit=80)
    target_3 = ngrams(target_text, 3)
    target_4 = ngrams(target_text, 4)
    findings: list[dict] = []

    for book in books:
        source_text = book_to_text(book)
        source_keywords = top_keywords(source_text, limit=80)
        token_overlap = overlap_items(target_keywords, source_keywords, limit=15)
        hook_overlap = [w for w in HOOK_WORDS if w in target_text and w in source_text]
        fuzzy = fuzz.token_set_ratio(target_text[:6000], source_text[:3000])
        seq = fuzz.partial_ratio(target_text[:6000], source_text[:3000])
        j3 = jaccard(target_3, ngrams(source_text, 3)) * 100
        j4 = jaccard(target_4, ngrams(source_text, 4)) * 100
        keyword_score = min(100.0, len(token_overlap) * 7 + len(hook_overlap) * 10)
        title_candidates = outline_title_candidates(outline)
        title_score = max((fuzz.ratio(t, book.title) for t in title_candidates), default=0)

        combined = max(
            fuzzy * 0.45 + seq * 0.15 + j3 * 0.15 + keyword_score * 0.2 + title_score * 0.05,
            keyword_score * 0.72 + j4 * 0.28,
        )
        if combined < min_score:
            continue
        level = risk_level(combined)
        overlaps = list(dict.fromkeys(hook_overlap + token_overlap))[:15]
        findings.append(
            {
                "risk_level": level,
                "score": round(combined, 1),
                "title": book.title,
                "author": book.author,
                "category": book.category,
                "rank_name": book.rank_name,
                "rank_no": book.rank_no,
                "heat": book.heat,
                "source_url": book.source_url,
                "overlap_hooks": hook_overlap,
                "overlap_keywords": token_overlap,
                "reason": " / ".join(overlaps[:8]) if overlaps else "整体文本结构或简介语义相近",
                "advice": advice_for_finding(level, overlaps),
                "metrics": {
                    "fuzzy": round(fuzzy, 1),
                    "partial": round(seq, 1),
                    "ngram3": round(j3, 1),
                    "ngram4": round(j4, 1),
                    "keyword": round(keyword_score, 1),
                    "title": round(title_score, 1),
                },
            }
        )
    findings.sort(key=lambda x: (x["score"], x.get("heat") or 0), reverse=True)
    return findings[:top_n]


def report_to_markdown(outline_name: str, findings: list[dict], sample_size: int) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"# 大纲防撞审查报告：{outline_name}",
        "",
        f"- 生成时间：{now}",
        f"- 对比样本数：{sample_size}",
        f"- 命中风险数：{len(findings)}",
        "",
        "> 说明：本报告仅基于本地采集的番茄公开元数据（书名、简介、标签、热度等）做相似度预警，不代表法律结论，也不使用/抓取正文。",
        "",
    ]
    if not findings:
        lines.append("未发现明显撞文风险。")
        return "\n".join(lines) + "\n"

    lines.extend(["## 风险列表", ""])
    for i, f in enumerate(findings, 1):
        lines.extend(
            [
                f"### {i}. [{f['risk_level']}] {f['title']}",
                "",
                f"- 作者：{f.get('author') or '-'}",
                f"- 分类/榜单：{f.get('category') or '-'} / {f.get('rank_name') or '-'} / 排名 {f.get('rank_no') or '-'}",
                f"- 综合分：{f['score']}",
                f"- 重合点：{f.get('reason') or '-'}",
                f"- 建议：{f.get('advice') or '-'}",
                f"- 来源：{f.get('source_url') or '-'}",
                f"- 指标：`{json.dumps(f.get('metrics', {}), ensure_ascii=False)}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def save_collision_report(outline_name: str, findings: list[dict], sample_size: int) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_.-]+", "_", outline_name)[:40] or "outline"
    path = REVIEW_DIR / f"{stamp}_{safe}_collision_review.md"
    path.write_text(report_to_markdown(outline_name, findings, sample_size), encoding="utf-8")
    return path
