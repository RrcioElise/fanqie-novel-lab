from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from ..config import CONFIG_DIR

PUA_RE = re.compile(r"[\ue000-\uf8ff]")
FONT_CACHE_DIR = CONFIG_DIR / "font_cache"
FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Prefer fonts whose glyph outlines are close to Fanqie's webfont.
SYSTEM_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]

# A compact common-character prior. It helps distinguish visually similar rare chars
# such as 怏/快 without relying on an external language model.
COMMON_CHARS = (
    "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动"
    "同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化"
    "高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天"
    "政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向"
    "道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题程展五果料象员革位"
    "入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别手角期根"
    "论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七"
    "海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打"
    "白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话"
    "米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复"
    "容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克"
    "何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片"
    "始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞乐妹直播势曝伍部队"
    "黑名单每天千万只能城花库限加钓鱼佬排爆竿满级闯甲掉"
)




PHRASE_FIXES = {
    "宣播": "直播",
    "宣头疼": "直头疼",
    "宣接": "直接",
    "凤夫凰": "凤失凰",
    "夫去": "失去",
    "夫望": "失望",
    "夫败": "失败",
    "冂号": "口号",
    "固来": "回来",
    "固到": "回到",
    "作乩": "作战",
    "乩斗": "战斗",
    "字渣": "学渣",
    "字神": "学神",
    "字业": "学业",
    "字历": "学历",
    "字府": "学府",
    "字术": "学术",
    "主活": "生活",
}


def fix_decoded_text(text: str) -> str:
    for wrong, right in PHRASE_FIXES.items():
        text = text.replace(wrong, right)
    return text


def contains_pua(text: str) -> bool:
    return bool(PUA_RE.search(text or ""))


@lru_cache(maxsize=1)
def candidate_chars() -> list[str]:
    chars: list[str] = []
    seen: set[str] = set()
    for high in range(0xB0, 0xF8):
        for low in range(0xA1, 0xFF):
            try:
                ch = bytes([high, low]).decode("gb2312")
            except Exception:
                continue
            if "\u4e00" <= ch <= "\u9fff" and ch not in seen:
                seen.add(ch)
                chars.append(ch)
    # Ensure common chars are included even if not in GB2312 edge cases.
    for ch in COMMON_CHARS:
        if "\u4e00" <= ch <= "\u9fff" and ch not in seen:
            seen.add(ch)
            chars.append(ch)
    return chars


def _common_bonus_penalty(ch: str) -> float:
    idx = COMMON_CHARS.find(ch)
    if idx < 0:
        return 0.42
    return min(idx / 5000.0, 0.18)


def extract_font_url_from_html(html: str, base_url: str = "https://fanqienovel.com") -> str | None:
    # Prefer OTF because Pillow can load it directly.
    urls = re.findall(r'url\((https?:[^)\'"]+?\.(?:otf|ttf|woff2|woff))\)', html)
    if not urls:
        urls = re.findall(r"(https?:[^'\"()]+?\.(?:otf|ttf|woff2|woff))", html)
    for suffix in (".otf", ".ttf", ".woff2", ".woff"):
        for url in urls:
            clean = url.replace("\\u002F", "/").strip('"\'')
            if clean.endswith(suffix):
                return urljoin(base_url, clean)
    return None


def download_font(font_url: str) -> Path:
    digest = hashlib.sha1(font_url.encode("utf-8")).hexdigest()[:16]
    suffix = Path(font_url.split("?")[0]).suffix or ".otf"
    path = FONT_CACHE_DIR / f"{digest}{suffix}"
    if path.exists() and path.stat().st_size > 0:
        return path
    resp = requests.get(font_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def _render_char(ch: str, font: ImageFont.FreeTypeFont, size: int = 72, out: int = 40) -> np.ndarray:
    canvas = 112
    im = Image.new("L", (canvas, canvas), 255)
    d = ImageDraw.Draw(im)
    bbox = d.textbbox((0, 0), ch, font=font)
    x = (canvas - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (canvas - (bbox[3] - bbox[1])) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)
    return np.array(im.resize((out, out)), dtype=np.float32).reshape(-1)


@lru_cache(maxsize=1)
def _system_font_arrays() -> tuple[list[str], list[np.ndarray]]:
    chars = candidate_chars()
    arrays: list[np.ndarray] = []
    for font_path in SYSTEM_FONT_CANDIDATES:
        if not Path(font_path).exists():
            continue
        try:
            font = ImageFont.truetype(font_path, 72)
            arr = np.stack([_render_char(ch, font) for ch in chars])
            arrays.append(arr)
        except Exception:
            continue
    return chars, arrays


class FanqieFontDecoder:
    def __init__(self, font_url: str):
        self.font_url = font_url
        self.font_path = download_font(font_url)
        self.font = ImageFont.truetype(str(self.font_path), 72)
        self.cache_path = FONT_CACHE_DIR / f"map_{hashlib.sha1(font_url.encode('utf-8')).hexdigest()[:16]}.json"
        self.mapping: dict[str, str] = {}
        if self.cache_path.exists():
            try:
                self.mapping = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                self.mapping = {}

    def save(self) -> None:
        self.cache_path.write_text(json.dumps(self.mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    def decode_char(self, ch: str) -> str:
        if not contains_pua(ch):
            return ch
        if ch in self.mapping:
            return self.mapping[ch]
        chars, font_arrays = _system_font_arrays()
        if not font_arrays:
            return ch
        target = _render_char(ch, self.font)
        scores = np.zeros(len(chars), dtype=np.float32)
        for arr in font_arrays:
            mse = ((arr - target) ** 2).mean(axis=1)
            mn = float(mse.min())
            sd = float(mse.std()) or 1.0
            scores += (mse - mn) / sd
        scores = scores / max(len(font_arrays), 1)
        prior = np.array([_common_bonus_penalty(c) for c in chars], dtype=np.float32)
        final = scores + prior
        best_idx = int(final.argmin())
        decoded = chars[best_idx]
        self.mapping[ch] = decoded
        return decoded

    def decode_text(self, text: str) -> str:
        if not contains_pua(text or ""):
            return text
        decoded = "".join(self.decode_char(ch) for ch in text)
        decoded = fix_decoded_text(decoded)
        # Persist incrementally; mapping is tiny (usually <= 400 glyphs).
        self.save()
        return decoded


def build_decoder_from_html(html: str, base_url: str = "https://fanqienovel.com") -> FanqieFontDecoder | None:
    font_url = extract_font_url_from_html(html, base_url=base_url)
    if not font_url:
        return None
    try:
        return FanqieFontDecoder(font_url)
    except Exception:
        return None
