from __future__ import annotations

import json

from ..llm import chat_json, is_llm_configured
from ..prompts import TREND_SYSTEM, TREND_USER
from ..schemas import BookMeta, TrendReport


def compact_samples(books: list[BookMeta], max_items: int = 80) -> list[dict]:
    samples = []
    for book in books[:max_items]:
        samples.append(
            {
                "rank_no": book.rank_no,
                "category": book.category,
                "title": book.title,
                "description": book.description[:220],
                "tags": book.tags,
                "word_count": book.word_count,
                "heat": book.heat,
                "score": book.score,
                "status": book.status,
            }
        )
    return samples


def analyze_trends(genre: str, books: list[BookMeta]) -> TrendReport:
    if not books:
        # No fake market data: keep the report empty and let the UI tell the user to crawl/import real metadata.
        return TrendReport(
            genre=genre,
            sample_size=0,
            hot_patterns=[],
            common_hooks=[],
            reader_expectations=[],
            avoid_cliches=[],
            originality_opportunities=[],
            recommended_outline_rules=[],
        )
    if not is_llm_configured():
        # Real samples exist, but no model is configured. Do not fabricate conclusions.
        return TrendReport(
            genre=genre,
            sample_size=len(books),
            hot_patterns=[],
            common_hooks=[],
            reader_expectations=[],
            avoid_cliches=[],
            originality_opportunities=[],
            recommended_outline_rules=[],
        )
    user = TREND_USER.format(
        genre=genre,
        samples_json=json.dumps(compact_samples(books), ensure_ascii=False, indent=2),
    )
    data = chat_json(TREND_SYSTEM, user)
    data.setdefault("genre", genre)
    data.setdefault("sample_size", len(books))
    return TrendReport(**data)
