from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import get_settings
from .schemas import BookMeta


BOOK_COLUMNS = [
    "source_url",
    "rank_name",
    "rank_no",
    "category",
    "title",
    "author",
    "description",
    "tags",
    "word_count",
    "heat",
    "score",
    "status",
    "updated_at",
    "collected_at",
]


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                rank_name TEXT,
                rank_no INTEGER,
                category TEXT,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                tags TEXT,
                word_count INTEGER,
                heat REAL,
                score REAL,
                status TEXT,
                updated_at TEXT,
                collected_at TEXT,
                UNIQUE(title, author, source_url)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                genre TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def upsert_books(books: list[BookMeta]) -> int:
    init_db()
    count = 0
    with connect() as conn:
        for book in books:
            data = book.model_dump()
            data["tags"] = json.dumps(data.get("tags") or [], ensure_ascii=False)
            values = [data.get(col) for col in BOOK_COLUMNS]
            placeholders = ",".join("?" for _ in BOOK_COLUMNS)
            update_clause = ",".join(f"{col}=excluded.{col}" for col in BOOK_COLUMNS if col not in {"title", "author", "source_url"})
            sql = f"""
                INSERT INTO books ({','.join(BOOK_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT(title, author, source_url) DO UPDATE SET {update_clause}
            """
            conn.execute(sql, values)
            count += 1
        conn.commit()
    return count


def list_books(limit: int = 200, category: str | None = None) -> list[BookMeta]:
    init_db()
    with connect() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM books WHERE category LIKE ? ORDER BY COALESCE(heat, score, 0) DESC, id DESC LIMIT ?",
                (f"%{category}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM books ORDER BY COALESCE(heat, score, 0) DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    books: list[BookMeta] = []
    for row in rows:
        item = dict(row)
        item.pop("id", None)
        raw_tags = item.get("tags") or "[]"
        try:
            item["tags"] = json.loads(raw_tags)
        except json.JSONDecodeError:
            item["tags"] = [t.strip() for t in raw_tags.replace(";", ",").split(",") if t.strip()]
        books.append(BookMeta(**item))
    return books


def save_outline(title: str, genre: str, payload: dict) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO outlines (title, genre, payload_json) VALUES (?, ?, ?)",
            (title, genre, json.dumps(payload, ensure_ascii=False, indent=2)),
        )
        conn.commit()
        return int(cur.lastrowid)


def clear_books(only_sample: bool = False) -> int:
    init_db()
    with connect() as conn:
        if only_sample:
            cur = conn.execute("DELETE FROM books WHERE title LIKE '示例书名%' OR author='示例作者'")
        else:
            cur = conn.execute("DELETE FROM books")
        conn.commit()
        return int(cur.rowcount or 0)
