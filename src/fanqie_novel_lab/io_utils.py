from __future__ import annotations

import pandas as pd

from .schemas import BookMeta


def parse_tags(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value).replace("，", ";").replace(",", ";").split(";") if x.strip()]


def books_from_dataframe(df: pd.DataFrame) -> list[BookMeta]:
    books: list[BookMeta] = []
    for _, row in df.fillna("").iterrows():
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        books.append(
            BookMeta(
                source_url=str(row.get("source_url", "")),
                rank_name=str(row.get("rank_name", "")),
                rank_no=int(row["rank_no"]) if str(row.get("rank_no", "")).strip().isdigit() else None,
                category=str(row.get("category", "")),
                title=title,
                author=str(row.get("author", "")),
                description=str(row.get("description", "")),
                tags=parse_tags(row.get("tags", "")),
                word_count=int(row["word_count"]) if str(row.get("word_count", "")).strip().isdigit() else None,
                heat=float(row["heat"]) if str(row.get("heat", "")).strip() else None,
                score=float(row["score"]) if str(row.get("score", "")).strip() else None,
                status=str(row.get("status", "")),
                updated_at=str(row.get("updated_at", "")),
            )
        )
    return books


def books_from_csv(path: str) -> list[BookMeta]:
    df = pd.read_csv(path)
    return books_from_dataframe(df)
