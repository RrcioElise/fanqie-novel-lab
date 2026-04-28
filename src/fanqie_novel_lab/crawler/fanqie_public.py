from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..config import get_settings
from ..schemas import BookMeta
from .font_decoder import build_decoder_from_html, contains_pua

ALLOWED_HOSTS = {"fanqienovel.com", "www.fanqienovel.com"}
BASE_URL = "https://fanqienovel.com"
CATEGORY_CONFIG_URL = f"{BASE_URL}/api/config/list"
RANK_API_URL = f"{BASE_URL}/api/rank/category/list"

RANK_MOLD_LABELS = {
    1: "阅读榜",
    2: "新书榜",
}
GENDER_LABELS = {
    0: "女频",
    1: "男频",
}

PRIVATE_FONT_RE = re.compile(r"[\ue000-\uf8ff]")


def has_private_font_chars(text: str) -> bool:
    return bool(PRIVATE_FONT_RE.search(text or ""))


def private_font_ratio(text: str) -> float:
    if not text:
        return 0.0
    chars = [c for c in text if c.strip()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if PRIVATE_FONT_RE.match(c)) / len(chars)


def _assert_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只允许 http/https URL")
    if parsed.netloc not in ALLOWED_HOSTS:
        raise ValueError(f"当前采集器只允许番茄公开页面元数据：{ALLOWED_HOSTS}")


def _headers(referer: str = BASE_URL) -> dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.crawler_user_agent or "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Referer": referer,
    }


def _sleep() -> None:
    settings = get_settings()
    time.sleep(max(settings.crawler_delay_seconds, 0))


def normalize_tags(text: str) -> list[str]:
    raw = text or ""
    # Capture bracket tags like 【系统】【爽文】 when available.
    tags = re.findall(r"[【\[]([^】\]]{1,12})[】\]]", raw)
    if not tags:
        tags = re.split(r"[;,，、|/\s]+", raw)
    clean: list[str] = []
    for tag in tags:
        tag = tag.strip()
        if not tag or has_private_font_chars(tag):
            continue
        if tag not in clean:
            clean.append(tag)
        if len(clean) >= 10:
            break
    return clean


def parse_heat(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        if text.endswith("万"):
            return float(text[:-1]) * 10000
        return float(text)
    except ValueError:
        return None


def creation_status_text(value: object) -> str:
    return {"0": "完结", "1": "连载中", "2": "暂停"}.get(str(value), str(value or ""))


def fetch_rank_categories() -> list[dict]:
    """Fetch public rank categories from Fanqie config endpoint."""
    _sleep()
    resp = requests.get(
        CATEGORY_CONFIG_URL,
        params={"config_key": "serial_rank_category_list_common"},
        headers=_headers(f"{BASE_URL}/rank/all"),
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or "获取分类失败")
    rows = data.get("data", {}).get("list", []) or []
    result: list[dict] = []
    for row in rows:
        groups = row.get("group") or []
        for group in groups:
            result.append({"gender": 1 if group == "male" else 0, "gender_name": "男频" if group == "male" else "女频", "id": str(row.get("id")), "name": row.get("name", "")})
    return result


def crawl_rank_api(category_id: str, gender: int = 1, rank_mold: int = 1, limit: int = 50, offset: int = 0) -> list[BookMeta]:
    """Crawl Fanqie public rank metadata via the public category list API.

    只保存榜单元数据：书名、作者、简介、在读数、字数、更新标题等。
    不抓正文、不请求章节内容、不绕登录/验证码/付费限制。
    """
    books: list[BookMeta] = []
    page_size = min(max(limit, 1), 50)
    current_offset = offset
    category_name = ""
    try:
        categories = fetch_rank_categories()
        for c in categories:
            if c["id"] == str(category_id) and int(c["gender"]) == int(gender):
                category_name = c["name"]
                break
    except Exception:
        category_name = str(category_id)

    decoder = None
    rank_page_url = f"{BASE_URL}/rank/{gender}_{rank_mold}_{category_id}"
    try:
        _sleep()
        html_resp = requests.get(rank_page_url, headers=_headers(rank_page_url), timeout=20)
        if html_resp.ok:
            decoder = build_decoder_from_html(html_resp.text, base_url=BASE_URL)
    except Exception:
        decoder = None

    while len(books) < limit:
        take = min(page_size, limit - len(books))
        _sleep()
        params = {
            "app_id": 2503,
            "rank_list_type": 3,
            "offset": current_offset,
            "limit": take,
            "category_id": str(category_id),
            "rank_version": "",
            "gender": int(gender),
            "rankMold": int(rank_mold),
        }
        referer = f"{BASE_URL}/rank/{gender}_{rank_mold}_{category_id}"
        resp = requests.get(RANK_API_URL, params=params, headers=_headers(referer), timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(data.get("message") or "榜单接口返回失败")
        items = data.get("data", {}).get("book_list", []) or []
        if not items:
            break
        for item in items:
            book_id = str(item.get("bookId") or item.get("book_id") or "")
            title = unescape(str(item.get("bookName") or item.get("book_name") or "")).strip()
            author = unescape(str(item.get("author") or "")).strip()
            desc = unescape(str(item.get("abstract") or item.get("description") or "")).strip()
            rank_no = item.get("currentPos") or item.get("rank") or (current_offset + len(books) + 1)
            last_title = str(item.get("lastChapterTitle") or "").strip()
            raw_has_pua = any(contains_pua(x) for x in [title, author, desc, last_title])
            if decoder:
                title = decoder.decode_text(title)
                author = decoder.decode_text(author)
                desc = decoder.decode_text(desc)
                last_title = decoder.decode_text(last_title)
            rank_name = f"{GENDER_LABELS.get(int(gender), gender)}-{RANK_MOLD_LABELS.get(int(rank_mold), rank_mold)}"
            tags = normalize_tags(desc)
            tags.extend([x for x in [category_name, rank_name] if x and x not in tags])
            if has_private_font_chars(title + author + desc):
                tags.append("字体加密待人工校对")
            elif raw_has_pua:
                tags.append("字体已解码")
            meta = BookMeta(
                source_url=f"{BASE_URL}/page/{book_id}" if book_id else referer,
                rank_name=rank_name,
                rank_no=int(rank_no) if str(rank_no).isdigit() else None,
                category=category_name or str(category_id),
                title=title or f"book-{book_id}",
                author=author,
                description=desc,
                tags=tags,
                word_count=int(item.get("wordNumber") or 0) or None,
                heat=parse_heat(item.get("read_count") or item.get("readCount")),
                score=None,
                status=creation_status_text(item.get("creationStatus")),
                updated_at=str(item.get("lastChapterUpdateTime") or ""),
            )
            books.append(meta)
            if len(books) >= limit:
                break
        if len(items) < take:
            break
        current_offset += len(items)
    return books


def parse_public_rank_html(html: str, source_url: str, limit: int = 50) -> list[BookMeta]:
    """Parse public ranking page metadata only as a fallback."""
    soup = BeautifulSoup(html, "html.parser")
    decoder = build_decoder_from_html(html, base_url=BASE_URL)
    books: list[BookMeta] = []
    seen: set[tuple[str, str]] = set()

    items = soup.select(".rank-book-item")
    if items:
        for idx, item in enumerate(items, start=1):
            title_a = item.select_one(".title a[href]")
            author_a = item.select_one(".author a")
            desc_el = item.select_one(".desc")
            status_el = item.select_one(".book-item-footer-status")
            count_el = item.select_one(".book-item-count")
            if not title_a:
                continue
            href = title_a.get("href", "")
            title = title_a.get_text(" ", strip=True)
            author = author_a.get_text(" ", strip=True) if author_a else ""
            desc = desc_el.get_text("\n", strip=True) if desc_el else ""
            raw_has_pua = any(contains_pua(x) for x in [title, author, desc])
            if decoder:
                title = decoder.decode_text(title)
                author = decoder.decode_text(author)
                desc = decoder.decode_text(desc)
            key = (title, href)
            if key in seen:
                continue
            seen.add(key)
            heat = None
            if count_el:
                m = re.search(r"在读[:：]?\s*([0-9.]+万?)", count_el.get_text(" ", strip=True))
                heat = parse_heat(m.group(1)) if m else None
            tags = normalize_tags(desc)
            if has_private_font_chars(title + author + desc):
                tags.append("字体加密待人工校对")
            elif raw_has_pua:
                tags.append("字体已解码")
            books.append(
                BookMeta(
                    source_url=urljoin(BASE_URL, href),
                    rank_name="public_rank_html",
                    rank_no=idx,
                    title=title,
                    author=author,
                    description=desc,
                    tags=tags,
                    heat=heat,
                    status=status_el.get_text(" ", strip=True) if status_el else "",
                )
            )
            if len(books) >= limit:
                break
        return books

    # Conservative parser: collect links that look like public book pages.
    candidates = soup.find_all("a", href=True)
    rank_no = 0
    for a in candidates:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        title = a.get("title") or a.get("aria-label") or text
        title = re.sub(r"\s+", " ", title or "").strip()
        if not title or len(title) < 2:
            continue
        if not ("/page/" in href or "/book/" in href):
            continue
        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        rank_no += 1
        desc = ""
        parent = a.find_parent()
        if parent:
            desc = parent.get_text(" ", strip=True).replace(title, "", 1).strip()[:300]
            raw_has_pua = raw_has_pua or contains_pua(desc)
            if decoder:
                desc = decoder.decode_text(desc)
        tags = normalize_tags(desc)
        if has_private_font_chars(title + desc):
            tags.append("字体加密待人工校对")
        elif raw_has_pua:
            tags.append("字体已解码")
        books.append(
            BookMeta(
                source_url=urljoin(BASE_URL, href),
                rank_name="public_rank_html",
                rank_no=rank_no,
                title=title[:80],
                description=desc,
                tags=tags,
            )
        )
        if len(books) >= limit:
            break
    return books


def crawl_public_metadata(url: str, limit: int = 50) -> list[BookMeta]:
    """Fetch a public page and parse metadata only; no login, no anti-bot bypass, no chapter text."""
    _assert_allowed_url(url)
    # If this is a known rank URL, prefer the public JSON API.
    m = re.search(r"/rank/(\d+)_(\d+)_(\d+)", url)
    if m:
        gender, rank_mold, category_id = m.groups()
        return crawl_rank_api(category_id=category_id, gender=int(gender), rank_mold=int(rank_mold), limit=limit)

    _sleep()
    resp = requests.get(url, headers=_headers(url), timeout=20)
    resp.raise_for_status()
    return parse_public_rank_html(resp.text, source_url=url, limit=limit)
