from __future__ import annotations

from rapidfuzz import fuzz

from ..schemas import BookMeta, NovelOutline


def check_outline_similarity(outline: NovelOutline, books: list[BookMeta], threshold: int = 72) -> list[dict]:
    """Simple anti-collision guard.

    这不是法律判断，只是帮助发现“简介/卖点过于相似”的风险。
    """
    target_text = "\n".join(
        [
            outline.one_line_pitch,
            outline.world_setting,
            " ".join(outline.selling_points),
            " ".join(outline.power_system_or_hook_rules),
        ]
    )
    findings: list[dict] = []
    for book in books:
        source_text = "\n".join([book.title, book.description, " ".join(book.tags)])
        score = fuzz.token_set_ratio(target_text, source_text)
        if score >= threshold:
            findings.append(
                {
                    "title": book.title,
                    "author": book.author,
                    "score": score,
                    "reason": "大纲卖点/设定与公开简介或标签相似度偏高，建议调整核心设定。",
                }
            )
    return sorted(findings, key=lambda x: x["score"], reverse=True)
