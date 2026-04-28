from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from fanqie_novel_lab.config import CHAPTER_DIR, CONFIG_DIR, OUTLINE_DIR, OUTPUT_DIR, PUBLISH_DIR, REVIEW_DIR, get_settings
from fanqie_novel_lab.crawler.fanqie_public import crawl_public_metadata, crawl_rank_api, fetch_rank_categories
from fanqie_novel_lab.db import clear_books, connect, init_db, list_books, upsert_books
from fanqie_novel_lab.io_utils import books_from_dataframe
from fanqie_novel_lab.model_profiles import (
    PRESET_BASE_URLS,
    PROFILES_PATH,
    ModelProfile,
    delete_profile,
    fetch_models,
    get_active_profile,
    is_profile_usable,
    list_profiles,
    set_active_profile,
    upsert_profile,
)
from fanqie_novel_lab.schemas import ChapterDraft, ChapterReview, NovelOutline, OutlineReview, TopicBrief
from fanqie_novel_lab.services.chapter_reviewer import (
    audit_chapter_against_outline,
    audit_to_markdown,
    list_chapter_audit_files,
    save_chapter_audit,
)
from fanqie_novel_lab.services.chapter_generator import (
    chapter_plan_from_outline,
    chapter_to_markdown,
    content_length,
    generate_chapter_series,
    list_chapter_files,
    load_chapter_from_path,
    polish_chapter,
    save_chapter_files,
)
from fanqie_novel_lab.services.collision_reviewer import (
    compare_outline_to_books,
    report_to_markdown,
    save_collision_report,
)
from fanqie_novel_lab.services.publisher import (
    FANQIE_WRITER_ZONE_URL,
    PublishPackage,
    WorkProfile,
    list_publish_packages,
    list_work_profiles,
    package_from_chapter,
    package_to_markdown,
    package_to_txt,
    safe_name,
    save_publish_package,
    save_work_profile,
    update_package_status,
    validate_publish_package,
    work_from_outline,
)
from fanqie_novel_lab.services.outline_generator import (
    generate_outline,
    outline_to_markdown,
    polish_outline,
    save_outline_files,
)
from fanqie_novel_lab.services.open_source_readiness import (
    readiness_markdown,
    readiness_rows,
    readiness_summary,
    scan_open_source_readiness,
)
from fanqie_novel_lab.services.similarity_guard import check_outline_similarity
from fanqie_novel_lab.services.trend_analyzer import analyze_trends
from fanqie_novel_lab.writing_skills import (
    ALL_WRITING_SKILLS,
    DEFAULT_WRITING_SKILL_IDS,
    format_skill_constraints,
    selected_skill_names,
    skill_label,
)

st.set_page_config(page_title="Fanqie Novel Lab", page_icon="🍅", layout="wide")
init_db()

POLISH_MODES = [
    "加强前三章爆点",
    "强化主角动机",
    "金手指规则与代价",
    "反派压迫感",
    "节奏压缩",
    "降低 AI 味",
    "番茄平台适配",
    "原创防撞",
    "卷纲连载性",
    "标题与卖点",
]

THEME_CSS = """
<style>
:root {
  --bg: #f6f5f2;
  --surface: #ffffff;
  --surface-subtle: #fbfaf7;
  --ink: #111318;
  --ink-2: #2b2f36;
  --muted: #6f7480;
  --muted-2: #a0a4ad;
  --line: #e6e2dc;
  --line-strong: #d8d2ca;
  --accent: #ef3e2e;
  --accent-2: #ff7a59;
  --accent-soft: #fff1ed;
  --green: #16825d;
  --green-soft: #eaf7f1;
  --amber: #a66500;
  --amber-soft: #fff5df;
  --dark: #14161c;
  --shadow: 0 12px 30px rgba(18, 16, 12, .07);
  --radius: 14px;
  --radius-lg: 18px;
}
html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
}
.stApp {
  color: var(--ink);
  background: linear-gradient(180deg, #f8f7f4 0%, #f2f0eb 100%);
}
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; }
.block-container { max-width: 1280px; padding: 1.05rem 1.25rem 3rem; }

/* App shell */
[data-testid="stSidebar"] > div:first-child {
  width: 280px;
  background: #111318;
  color: rgba(255,255,255,.88);
  border-right: 1px solid rgba(255,255,255,.08);
  box-shadow: 14px 0 34px rgba(12, 12, 16, .18);
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display:none; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] .stCaptionContainer { color: rgba(255,255,255,.58); }
.sidebar-brand { display:flex; align-items:center; gap:11px; padding: 6px 0 16px; margin-bottom: 12px; border-bottom:1px solid rgba(255,255,255,.10); }
.sidebar-logo { width:34px; height:34px; border-radius:10px; display:grid; place-items:center; background:#fff; color:#111318; font-weight:950; letter-spacing:-.06em; }
.sidebar-brand-title { color:#fff; font-size:16px; font-weight:900; letter-spacing:-.04em; }
.sidebar-brand-sub { color:rgba(255,255,255,.54); font-size:11px; margin-top:1px; }
.sidebar-section-label { margin: 16px 0 6px; color: rgba(255,255,255,.36); font-size:10px; font-weight:900; letter-spacing:.14em; text-transform:uppercase; }
.sidebar-project { padding: 12px; border-radius: 14px; background: rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08); margin: 12px 0; }
.sidebar-project h4 { color:#fff; margin:0 0 5px; font-size:14px; }
.sidebar-project p { margin:2px 0; line-height:1.42; font-size:12px; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
  min-height:34px; padding: 7px 9px; margin:2px 0; border-radius: 10px !important;
  color: rgba(255,255,255,.78); font-weight:780; border:1px solid transparent;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover { background: rgba(255,255,255,.08); color:#fff; border-color:rgba(255,255,255,.08); }
[data-testid="stSidebar"] .stButton > button { border-color: rgba(255,255,255,.16); background: rgba(255,255,255,.07); color:#fff; }
[data-testid="stSidebar"] [data-baseweb="select"] > div { background: rgba(255,255,255,.08) !important; color:#fff !important; border-color: rgba(255,255,255,.12) !important; }
.top-nav {
  display:flex; align-items:center; justify-content:space-between; gap:10px;
  padding: 8px 0 12px; margin-bottom: 6px; border-bottom:1px solid var(--line);
}
.top-brand { display:flex; align-items:center; gap:9px; min-width:0; }
.top-logo { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; background:#111318; color:#fff; font-weight:950; letter-spacing:-.06em; }
.top-title { font-weight:950; letter-spacing:-.055em; line-height:1; white-space:nowrap; }
.top-sub { color:var(--muted); font-size:11px; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:280px; }
.top-links { display:flex; gap:5px; flex-wrap:wrap; justify-content:flex-end; }
.top-link { display:inline-flex; align-items:center; gap:5px; padding:6px 9px; border-radius:999px; color:var(--ink-2) !important; text-decoration:none !important; border:1px solid transparent; font-size:12px; font-weight:850; }
.top-link:hover { background:#fff; border-color:var(--line); }
.top-meta { display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin: 0 0 8px; }
.top-meta .pill { background:transparent; }

/* Typography */
h1,h2,h3,h4 { color: var(--ink); letter-spacing:-.035em; }
p { line-height:1.62; }
hr { border-color: var(--line); }

/* Mature compact masthead */
.page-head {
  position:relative; display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:end; gap:12px;
  padding: 0 0 12px; margin: 4px 0 10px; border-bottom:1px solid var(--line);
  background:transparent; box-shadow:none; border-radius:0;
}
.page-head:before { content:""; position:absolute; bottom:-1px; left:0; width:56px; height:2px; background:var(--accent); }
.page-head:after { display:none; }
.page-eyebrow, .hero-kicker, .section-kicker { color: var(--accent); font-size:10px; font-weight:950; letter-spacing:.14em; text-transform:uppercase; }
.page-title { margin-top:4px; font-size: clamp(25px, 3vw, 38px); font-weight:950; line-height:1.02; letter-spacing:-.065em; }
.page-desc { margin-top:5px; max-width:760px; color:var(--muted); font-size:13px; line-height:1.52; }
.page-badge, .pill, .hero-chip { display:inline-flex; align-items:center; gap:6px; padding:5px 9px; border-radius:999px; border:1px solid var(--line); background:var(--surface); color:var(--ink-2); font-size:12px; font-weight:800; white-space:nowrap; }
.page-badge { color:#b42318; background:var(--accent-soft); border-color:#ffd7cd; }
.chip-row { display:flex; align-items:center; flex-wrap:wrap; gap:7px 8px; margin:7px 0 2px; max-width:100%; }
.chip-row .pill { margin:0; line-height:1.18; max-width:100%; }
.chip-row .pill.more { background:var(--dark); color:#fff; border-color:var(--dark); padding-inline:10px; }
.chip-row.tight { gap:6px; margin-top:6px; }

/* Home masthead becomes command-center, not poster. */
.app-hero { border-radius: 20px; padding: 18px; margin-bottom: 12px; background: #15171d; color:#fff; box-shadow: var(--shadow); position:relative; overflow:hidden; }
.app-hero:after { content:""; position:absolute; width:260px; height:260px; right:-130px; top:-120px; border-radius:999px; background: radial-gradient(circle, rgba(239,62,46,.42), transparent 65%); }
.hero-layout { position:relative; z-index:1; display:grid; grid-template-columns:minmax(0,1.2fr) minmax(260px,.65fr); gap:16px; align-items:end; }
.app-hero .hero-kicker { color:#ffb29f; }
.hero-title { color:#fff; margin:6px 0 6px; font-size: clamp(28px, 4vw, 48px); line-height:1; font-weight:950; letter-spacing:-.07em; }
.hero-subtitle { color:rgba(255,255,255,.66); max-width:720px; font-size:13px; line-height:1.58; }
.hero-actions { display:flex; gap:7px; flex-wrap:wrap; margin-top:12px; }
.app-hero .hero-chip { background:rgba(255,255,255,.08); color:rgba(255,255,255,.82); border-color:rgba(255,255,255,.13); }
.hero-panel { border-radius:16px; padding:12px; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10); }
.hero-panel-title { color:rgba(255,255,255,.62); font-size:12px; font-weight:850; margin-bottom:8px; }
.hero-stat-row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
.hero-stat { padding:9px; border-radius:12px; background:rgba(255,255,255,.07); min-width:0; }
.hero-stat strong { display:block; color:#fff; font-size:18px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-.04em; }
.hero-stat span { display:block; color:rgba(255,255,255,.48); font-size:10px; margin-top:3px; }

/* Metrics: dense KPI strip instead of mini cards. */
.metric-bar { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:0; margin: 8px 0 14px; border:1px solid var(--line); border-radius:14px; overflow:hidden; background:var(--surface); }
.metric-item { min-width:0; padding:9px 10px; border-right:1px solid var(--line); background:var(--surface); }
.metric-item:last-child { border-right:0; }
.metric-label { color:var(--muted-2); font-size:10px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }
.metric-value { margin-top:2px; color:var(--ink); font-size:16px; font-weight:920; line-height:1.16; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.metric-hint { margin-top:2px; color:var(--muted); font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Sections: flat panes + dense rows */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 0 !important;
  border: 0 !important;
  border-bottom:1px solid var(--line) !important;
  background:transparent !important;
  box-shadow:none !important;
  padding: 0 !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] { gap:.55rem !important; }
[data-testid="stExpander"], div[data-testid="stForm"] { border-radius: var(--radius) !important; border:1px solid var(--line) !important; background:rgba(255,255,255,.58) !important; box-shadow:none !important; }
.section-kicker { margin-bottom:3px; }
.section-title { font-size:18px; font-weight:930; letter-spacing:-.045em; margin-bottom:2px; }
.section-desc { color:var(--muted); font-size:12px; line-height:1.42; margin-bottom:8px; }
.info-card, .empty-state, .phase-card, .risk-card, .asset-card { border-radius:10px; background:transparent; border:1px solid var(--line); box-shadow:none; }
.info-card { padding:9px 10px; margin-bottom:7px; }
.info-card h4 { margin:0 0 3px; font-size:14px; font-weight:900; }
.info-card p { margin:0; color:var(--muted); font-size:12px; line-height:1.42; }
.empty-state { padding:12px 13px; color:var(--muted); border-style:dashed; }
.empty-state strong { display:block; color:var(--ink); font-size:15px; margin-bottom:3px; }
.soft-note { padding:8px 10px; border-radius:12px; border:1px solid var(--line); background:var(--surface-subtle); color:var(--ink-2); font-size:12px; line-height:1.42; margin-bottom:8px; }
.code-path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color:var(--muted); font-size:11px; overflow-wrap:anywhere; padding:3px 0; }

/* Workflow rows */
.creation-flow { position:relative; margin: 10px 0 12px; padding: 14px 14px 12px; border:1px solid var(--line); border-radius:18px; background:linear-gradient(135deg, rgba(255,255,255,.78), rgba(251,248,242,.62)); overflow:hidden; }
.creation-flow:before { content:""; position:absolute; inset:-90px auto auto -80px; width:220px; height:220px; border-radius:999px; background:radial-gradient(circle, rgba(239,62,46,.12), transparent 62%); pointer-events:none; }
.creation-flow-head { position:relative; z-index:1; display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom:12px; }
.creation-flow-title { font-size:18px; font-weight:950; letter-spacing:-.05em; }
.creation-flow-sub { margin-top:2px; color:var(--muted); font-size:12px; }
.creation-flow-progress { min-width:180px; }
.creation-flow-progress-label { display:flex; align-items:baseline; justify-content:space-between; color:var(--muted); font-size:10px; font-weight:850; }
.creation-flow-progress-label b { color:var(--ink); font-size:16px; letter-spacing:-.05em; }
.creation-flow-bar { height:6px; margin-top:5px; border-radius:999px; background:#ebe7df; overflow:hidden; }
.creation-flow-fill { height:100%; border-radius:999px; background:linear-gradient(90deg, #111318, #ef3e2e); }
.creation-flow-track { position:relative; z-index:1; display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; }
.creation-flow-track:before { content:""; position:absolute; left:9%; right:9%; top:27px; height:1px; background:linear-gradient(90deg, transparent, var(--line-strong), transparent); z-index:0; }
.creation-step { position:relative; z-index:1; min-width:0; padding:10px 9px 9px; border:1px solid rgba(230,226,220,.86); border-radius:15px; background:rgba(255,255,255,.72); }
.creation-step.ready { border-color:rgba(22,130,93,.20); background:linear-gradient(180deg, rgba(234,247,241,.72), rgba(255,255,255,.78)); }
.creation-step.current { border-color:rgba(239,62,46,.32); box-shadow:inset 0 0 0 1px rgba(239,62,46,.08); }
.creation-step-top { display:flex; align-items:center; justify-content:space-between; gap:6px; margin-bottom:7px; }
.creation-step-no { width:24px; height:24px; display:grid; place-items:center; border-radius:8px; background:#111318; color:#fff; font-size:10px; font-weight:950; }
.creation-step.ready .creation-step-no { background:var(--green); }
.creation-step.current .creation-step-no { background:var(--accent); }
.creation-step-icon { width:24px; height:24px; display:grid; place-items:center; border-radius:8px; background:#f3f0ea; font-size:14px; }
.creation-step-title { font-size:13px; font-weight:930; letter-spacing:-.035em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.creation-step-desc { min-height:31px; color:var(--muted); font-size:11px; line-height:1.38; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.creation-step-state { display:inline-flex; margin-top:8px; padding:3px 7px; border-radius:999px; background:#f1efea; color:var(--muted); font-size:10px; font-weight:850; }
.creation-step.ready .creation-step-state { color:var(--green); background:var(--green-soft); }
.flow-jump-caption { color:var(--muted); font-size:11px; margin:6px 0 0; }

/* Export assets */
.asset-grid { display:grid; grid-template-columns:1fr; gap:7px; }
.asset-card { padding:9px 10px; min-height:auto; margin-bottom:7px; }
.asset-top { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px; }
.asset-title { font-weight:930; letter-spacing:-.035em; }
.asset-state { color:var(--muted); font-size:10px; font-weight:850; padding:3px 7px; border-radius:999px; background:#f1efea; }
.asset-card.ready .asset-state { color:var(--green); background:var(--green-soft); }
.asset-desc { color:var(--muted); font-size:12px; line-height:1.38; }
.check-list { display:grid; gap:7px; }
.check-row { display:flex; align-items:center; gap:8px; padding:7px 9px; border:1px solid var(--line); border-radius:12px; background:var(--surface); font-size:13px; }
.check-dot { width:18px; height:18px; border-radius:6px; display:grid; place-items:center; font-size:11px; background:#f1efea; color:var(--muted); flex:0 0 auto; }
.check-row.ok .check-dot { background:var(--green-soft); color:var(--green); }

/* Outline studio: single-column editor, no big cards. */
.outline-shell {
  padding: 2px 0 12px; margin: 2px 0 10px; border-bottom: 1px solid var(--line);
  background: transparent; box-shadow: none; border-radius: 0;
}
.outline-shell:after { display:none; }
.outline-shell-inner { display:block; }
.outline-kicker { color:var(--accent); font-size:10px; font-weight:950; letter-spacing:.14em; text-transform:uppercase; }
.outline-title { margin-top:4px; font-size: clamp(28px, 3.8vw, 42px); line-height:1; font-weight:960; letter-spacing:-.075em; }
.outline-desc { margin-top:6px; max-width:780px; color:var(--muted); font-size:13px; line-height:1.5; }
.outline-actions { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
.outline-pill { display:inline-flex; align-items:center; gap:5px; padding:4px 8px; border-radius:999px; border:1px solid var(--line); background:transparent; color:var(--ink-2); font-size:11px; font-weight:850; }
.outline-score { display:none; }
.outline-steps { display:flex; gap:6px; margin: 4px 0 12px; overflow-x:auto; padding-bottom:2px; scrollbar-width:none; }
.outline-steps::-webkit-scrollbar { display:none; }
.outline-step { flex:0 0 auto; padding:7px 10px; border:1px solid var(--line); border-radius:999px; background:transparent; }
.outline-step strong { display:block; font-size:12px; letter-spacing:-.02em; white-space:nowrap; }
.outline-step span { display:none; }
.outline-step.active { background:#111318; border-color:#111318; color:#fff; }
.editor-section { padding: 14px 0 16px; border-bottom: 1px solid var(--line); }
.editor-section:first-child { padding-top: 6px; }
.inline-action-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:8px; margin-top:8px; }
.compact-stack { display:grid; gap:8px; }
.editor-section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:10px; margin-bottom:10px; }
.editor-section-title { font-size:18px; font-weight:930; letter-spacing:-.045em; }
.editor-section-desc { margin-top:2px; color:var(--muted); font-size:12px; }
.editor-inline { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.editor-status-strip { display:grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap:6px; margin: 8px 0 0; }
.editor-status-item { padding:7px 8px; border:1px solid var(--line); border-radius:10px; background:rgba(255,255,255,.38); }
.editor-status-item b { display:block; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.editor-status-item span { display:block; margin-top:1px; color:var(--muted); font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.readiness-meter { padding:0; border:0; border-radius:0; background:transparent; }
.readiness-top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; }
.readiness-score { font-size:22px; font-weight:960; letter-spacing:-.06em; }
.readiness-label { color:var(--muted); font-size:11px; font-weight:850; }
.readiness-bar { margin-top:6px; height:5px; border-radius:999px; overflow:hidden; background:#ebe7df; }
.readiness-fill { height:100%; border-radius:999px; background:#111318; }
.check-list.compact { grid-template-columns: repeat(5, minmax(0, 1fr)); gap:6px; }
.check-list.compact .check-row { padding:6px 7px; font-size:12px; }
.outline-mini-list { display:grid; gap:6px; }
.outline-mini-row { display:flex; gap:8px; padding:7px 0; border-bottom:1px solid var(--line); background:transparent; }
.outline-mini-row:last-child { border-bottom:0; }
.outline-mini-no { width:24px; height:24px; border-radius:7px; display:grid; place-items:center; flex:0 0 auto; background:#111318; color:#fff; font-size:10px; font-weight:900; }
.outline-mini-title { font-weight:900; font-size:13px; }
.outline-mini-desc { color:var(--muted); font-size:11px; margin-top:1px; }

/* Lower visual weight: no boxed editor/cards on outline page. */
.editor-status-strip { border-top:1px solid var(--line); border-bottom:1px solid var(--line); gap:0; }
.editor-status-item { border:0; border-right:1px solid var(--line); border-radius:0; background:transparent; padding:8px 8px; }
.editor-status-item:last-child { border-right:0; }
div[data-testid="stForm"] { border:0 !important; background:transparent !important; box-shadow:none !important; padding:0 !important; }
[data-testid="stExpander"] { background:transparent !important; }

/* Controls */
[data-baseweb="tab-list"] { gap:5px; padding:4px; border-radius:12px; background:#e9e5de; border:1px solid var(--line); margin-bottom:12px; overflow-x:auto; scrollbar-width:none; }
[data-baseweb="tab-list"]::-webkit-scrollbar { display:none; }
[data-baseweb="tab"] { flex:0 0 auto; border-radius:9px !important; padding:7px 10px !important; min-height:32px; color:var(--muted); font-size:12px; font-weight:900; white-space:nowrap; }
[aria-selected="true"][data-baseweb="tab"] { color:#fff !important; background:var(--dark); }
[data-baseweb="tab-highlight"] { display:none; }

/* Segmented controls: top module tabs and quick jumps need breathing room. */
[data-testid="stButtonGroup"] {
  margin: .42rem 0 .92rem !important;
}
[data-testid="stButtonGroup"] div[role="radiogroup"] {
  gap:7px !important;
  row-gap:7px !important;
  flex-wrap:wrap !important;
  align-items:center !important;
}
[data-testid="stButtonGroup"] button[kind^="segmented_control"] {
  border-radius:10px !important;
  border:1px solid var(--line) !important;
  min-height:35px !important;
  padding:0 13px !important;
  margin:0 !important;
  background:rgba(255,255,255,.68) !important;
  box-shadow:0 1px 0 rgba(17,19,24,.035);
}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] {
  color:#fff !important;
  background:var(--dark) !important;
  border-color:var(--dark) !important;
}
[data-testid="stButtonGroup"] button[kind^="segmented_control"] p {
  font-weight:880 !important;
  letter-spacing:-.01em;
}

/* Button rhythm: Streamlit stacks buttons too tightly by default. */
[data-testid="stElementContainer"]:has(.stButton),
[data-testid="stElementContainer"]:has(.stFormSubmitButton),
[data-testid="stElementContainer"]:has(.stDownloadButton),
[data-testid="stElementContainer"]:has(.stLinkButton) {
  margin-top: .16rem !important;
  margin-bottom: .42rem !important;
}
[data-testid="stElementContainer"]:has(.stButton) + [data-testid="stElementContainer"]:has(.stButton),
[data-testid="stElementContainer"]:has(.stButton) + [data-testid="stElementContainer"]:has(.stDownloadButton),
[data-testid="stElementContainer"]:has(.stDownloadButton) + [data-testid="stElementContainer"]:has(.stDownloadButton),
[data-testid="stElementContainer"]:has(.stDownloadButton) + [data-testid="stElementContainer"]:has(.stButton),
[data-testid="stElementContainer"]:has(.stLinkButton) + [data-testid="stElementContainer"]:has(.stButton) {
  margin-top: .34rem !important;
}
div.stButton, div.stFormSubmitButton, div.stDownloadButton, div.stLinkButton { width:100%; }
div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button,
div.stLinkButton > a,
a[data-testid="stPageLink-NavLink"] {
  border-radius:11px !important;
  min-height:38px;
  padding: 0 14px !important;
  font-weight:880;
  letter-spacing:-.01em;
  box-shadow:0 1px 0 rgba(17,19,24,.04);
  transition: transform .12s ease, border-color .12s ease, background .12s ease;
}
div.stDownloadButton > button, div.stLinkButton > a {
  background:var(--surface-subtle) !important;
}
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"],
div.stDownloadButton > button[kind="primary"] {
  color:#fff;
  border:0;
  background:var(--dark);
  box-shadow:0 8px 18px rgba(17,19,24,.12);
}
div.stButton > button:hover,
div.stFormSubmitButton > button:hover,
div.stDownloadButton > button:hover,
div.stLinkButton > a:hover {
  transform:translateY(-1px);
  border-color:var(--line-strong);
}
div.stButton > button:disabled,
div.stFormSubmitButton > button:disabled,
div.stDownloadButton > button:disabled {
  opacity:.46;
  cursor:not-allowed;
  transform:none !important;
  background:#f0eee9 !important;
  color:var(--muted) !important;
  border-color:var(--line) !important;
  box-shadow:none !important;
}
.stTextInput, .stNumberInput, .stTextArea, .stSelectbox, .stSlider, .stFileUploader {
  margin-bottom:.35rem;
}
.stTextInput input, .stNumberInput input, textarea, [data-baseweb="select"] > div { border-radius:10px !important; border-color:var(--line) !important; background:var(--surface) !important; }
.stTextInput input::placeholder, textarea::placeholder { color:#b8b2aa !important; opacity:1 !important; }
.stDataFrame { border-radius:12px; overflow:hidden; border:1px solid var(--line); }
.stAlert { border-radius:12px; padding-block:8px; }

/* Mobile: no horizontal clipping, no poster-sized sections. */
@media (max-width: 760px) {
  .block-container { padding:.65rem .85rem 2.2rem; }
  .app-hero { padding:14px; border-radius:16px; }
  .hero-layout { grid-template-columns:1fr; }
  .hero-panel { display:none; }
  .hero-title { font-size:28px; }
  .hero-subtitle { font-size:12px; line-height:1.48; }
  .page-head { display:block; padding-bottom:10px; margin-top:2px; }
  .page-title { font-size:26px; }
  .page-desc { font-size:12px; line-height:1.42; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .page-badge { margin-top:7px; }
  .top-nav { display:block; padding-top:4px; }
  .top-links { justify-content:flex-start; margin-top:8px; overflow-x:auto; flex-wrap:nowrap; padding-bottom:2px; }
  .top-link { flex:0 0 auto; }
  .top-sub { max-width:260px; }
  .metric-bar { grid-template-columns:repeat(2,minmax(0,1fr)); border-radius:12px; margin-bottom:12px; }
  .metric-item { padding:7px 6px; }
  .metric-item:nth-child(2n) { border-right:0; }
  .metric-item:nth-child(n+3) { border-top:1px solid var(--line); }
  .metric-label { font-size:9px; letter-spacing:.03em; }
  .metric-value { font-size:13px; }
  .metric-hint { display:none; }
  [data-testid="stVerticalBlockBorderWrapper"] { border-radius:0 !important; }
  .section-title { font-size:17px; }
  .section-desc { font-size:12px; display:-webkit-box; -webkit-line-clamp:1; -webkit-box-orient:vertical; overflow:hidden; }
  .creation-flow { padding:12px 10px; border-radius:15px; }
  .creation-flow-head { display:block; }
  .creation-flow-progress { min-width:0; margin-top:9px; }
  .creation-flow-track { grid-template-columns:1fr; gap:7px; }
  .creation-flow-track:before { display:none; }
  .creation-step { display:grid; grid-template-columns:auto minmax(0,1fr); column-gap:8px; padding:8px; }
  .creation-step-top { grid-row:1 / span 2; display:grid; align-content:start; gap:5px; margin:0; }
  .creation-step-state { margin-top:5px; width:max-content; }
  .asset-grid { grid-template-columns:1fr; }
  .outline-shell { padding:0 0 10px; border-radius:0; }
  .outline-title { font-size:29px; }
  .outline-desc { font-size:12px; }
  .outline-steps { gap:5px; }
  .outline-step { padding:6px 9px; }
  .outline-step strong { font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .editor-section { padding:12px 0 14px; }
  .editor-section-head { display:block; }
  .editor-status-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .check-list.compact { grid-template-columns:repeat(2,minmax(0,1fr)); }
  [data-baseweb="tab"] { padding:7px 8px !important; font-size:12px; }
}
@media (max-width: 390px) {
  .metric-value { font-size:12px; }
  .creation-step-title { white-space:normal; }
}
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_rank_categories() -> list[dict]:
    return fetch_rank_categories()


def normalize_outline(value) -> NovelOutline | None:
    if value is None:
        return None
    if isinstance(value, NovelOutline):
        return value
    if isinstance(value, dict):
        return NovelOutline(**value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return NovelOutline(**model_dump())
    if isinstance(value, str):
        return NovelOutline(**json.loads(value))
    return None


def normalize_chapter(value) -> ChapterDraft | None:
    if value is None:
        return None
    if isinstance(value, ChapterDraft):
        return value
    if isinstance(value, dict):
        return ChapterDraft(**value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return ChapterDraft(**model_dump())
    if isinstance(value, str):
        return ChapterDraft(**json.loads(value))
    return None


def saved_outline_files() -> list[Path]:
    return sorted(OUTLINE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_outline_from_path(path: Path) -> NovelOutline:
    return NovelOutline(**json.loads(path.read_text(encoding="utf-8")))


def active_skill_ids() -> list[str]:
    return st.session_state.get("selected_writing_skill_ids", DEFAULT_WRITING_SKILL_IDS)


def active_skill_constraints(scope: str) -> str:
    return format_skill_constraints(active_skill_ids(), scope)


def inject_skill_text(base: str, scope: str, title: str = "客户端启用的创作技能约束") -> str:
    text = active_skill_constraints(scope)
    if not text:
        return base
    return (base or "").strip() + f"\n\n【{title}】\n" + text


def ui_escape(value) -> str:
    return html.escape(str(value or ""), quote=True)


def clip_text(value, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def file_table(paths: list[Path], limit: int = 12) -> list[dict]:
    rows = []
    for p in paths[:limit]:
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            mtime = ""
        rows.append({"文件": p.name, "修改时间": mtime, "路径": str(p)})
    return rows


def paired_output_files(path: Path) -> list[Path]:
    """Return the selected JSON plus same-stem assets created together."""
    files = [path]
    for suffix in [".md", ".txt"]:
        sidecar = path.with_suffix(suffix)
        if sidecar.exists() and sidecar not in files:
            files.append(sidecar)
    return files


def delete_output_files(path: Path, allowed_dir: Path) -> list[Path]:
    allowed_root = allowed_dir.resolve()
    target = path.resolve()
    target.relative_to(allowed_root)
    deleted: list[Path] = []
    for item in paired_output_files(target):
        resolved = item.resolve()
        resolved.relative_to(allowed_root)
        if resolved.exists() and resolved.is_file():
            resolved.unlink()
            deleted.append(resolved)
    return deleted


def reset_deleted_session_refs(deleted: list[Path]) -> None:
    deleted_text = {str(p) for p in deleted}
    if st.session_state.get("outline_saved_json") in deleted_text:
        for key in ["outline", "outline_saved_json", "outline_saved_md", "trend"]:
            st.session_state.pop(key, None)
    if st.session_state.get("edit_chapter_source") in deleted_text:
        for key in ["edit_chapter", "edit_chapter_source", "chapter_draft"]:
            st.session_state.pop(key, None)


def render_history_delete_panel(paths: list[Path], *, key_prefix: str, allowed_dir: Path, item_label: str) -> None:
    if not paths:
        return
    with st.expander(f"删除{item_label}", expanded=False):
        labels = []
        for p in paths:
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                mtime = ""
            labels.append(f"{p.name} · {mtime}")
        selected = st.selectbox(f"选择要删除的{item_label}", labels, key=f"{key_prefix}_delete_select")
        path = paths[labels.index(selected)]
        files = paired_output_files(path)
        st.markdown(
            "<div class='soft-note'>将删除以下本地文件，删除后不可从客户端恢复。</div>",
            unsafe_allow_html=True,
        )
        for item in files:
            st.markdown(f"<div class='code-path'>{ui_escape(item)}</div>", unsafe_allow_html=True)
        confirm = st.checkbox(f"我确认删除：{path.name}", key=f"{key_prefix}_delete_confirm")
        if st.button(f"删除选中的{item_label}", key=f"{key_prefix}_delete_button", disabled=not confirm, width="stretch"):
            try:
                deleted = delete_output_files(path, allowed_dir)
                reset_deleted_session_refs(deleted)
                st.success("已删除：" + "、".join(p.name for p in deleted))
                st.rerun()
            except Exception as exc:
                st.error(f"删除失败：{exc}")


def directory_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return round(total / 1024 / 1024, 3)


def database_status_rows() -> list[dict]:
    settings = get_settings()
    db_path = settings.db_path
    size_mb = round(db_path.stat().st_size / 1024 / 1024, 3) if db_path.exists() else 0
    rows: list[dict] = [
        {"项目": "SQLite 路径", "值": str(db_path), "说明": "本地数据库文件"},
        {"项目": "文件大小", "值": f"{size_mb} MB", "说明": "只统计 SQLite 文件"},
        {"项目": "数据目录", "值": str(db_path.parent), "说明": "数据库所在目录"},
    ]
    try:
        with connect() as conn:
            table_names = [
                r["name"]
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            ]
            for table in table_names:
                quoted_table = '"' + str(table).replace('"', '""') + '"'
                count = conn.execute(f"SELECT COUNT(*) AS c FROM {quoted_table}").fetchone()["c"]
                rows.append({"项目": f"表：{table}", "值": str(count), "说明": "记录数"})
    except Exception as exc:
        rows.append({"项目": "数据库状态", "值": "读取失败", "说明": str(exc)})
    return rows


def output_status_rows() -> list[dict]:
    dirs = [
        ("outlines", OUTLINE_DIR),
        ("chapters", CHAPTER_DIR),
        ("reviews", REVIEW_DIR),
        ("publishing", PUBLISH_DIR),
        ("config", CONFIG_DIR),
    ]
    return [
        {
            "目录": name,
            "文件数": len([p for p in path.glob("*") if p.is_file()]),
            "大小": f"{directory_size_mb(path)} MB",
            "路径": str(path),
        }
        for name, path in dirs
    ]


def books_table_rows(books: list) -> list[dict]:
    rows = []
    for b in books:
        rows.append(
            {
                "书名": b.title,
                "作者": b.author,
                "分类": b.category,
                "热度": b.heat,
                "评分": b.score,
                "字数": b.word_count,
                "标签": "、".join(b.tags[:5]),
                "简介": clip_text(b.description, 90),
                "来源": clip_text(b.source_url, 80),
            }
        )
    return rows


def model_profile_rows(profiles: list[ModelProfile]) -> list[dict]:
    rows: list[dict] = []
    active_name = get_active_profile().name
    for p in profiles:
        rows.append(
            {
                "当前": "●" if p.name == active_name else "",
                "配置": p.name,
                "Provider": "Claude CLI" if p.provider == "claude_cli" else "OpenAI-compatible",
                "模型": p.model,
                "Base URL": p.base_url,
                "Key": p.masked_key or "本地/未填",
                "状态": "可用" if is_profile_usable(p) else "待补全",
                "备注": p.note,
            }
        )
    return rows


def section_intro(kicker: str, title: str, desc: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-kicker">{ui_escape(kicker)}</div>
        <div class="section-title">{ui_escape(title)}</div>
        <div class="section-desc">{ui_escape(desc)}</div>
        """,
        unsafe_allow_html=True,
    )


def info_card(title: str, desc: str, *, icon: str = "", extra: str = "") -> None:
    st.markdown(
        f"""
        <div class="info-card">
          <h4>{ui_escape(icon)} {ui_escape(title)}</h4>
          <p>{ui_escape(desc)}</p>
          {extra}
        </div>
        """,
        unsafe_allow_html=True,
    )


def chips_html(items: list[str], limit: int = 8) -> str:
    chips = []
    for item in items[:limit]:
        if item:
            chips.append(f"<span class='pill'>{ui_escape(item)}</span>")
    if len(items) > limit:
        chips.append(f"<span class='pill more'>+{len(items) - limit}</span>")
    if not chips:
        return ""
    return "<div class='chip-row'>" + "".join(chips) + "</div>"


def render_hero() -> None:
    books_count = len(list_books(limit=10_000))
    outline_count = len(saved_outline_files())
    chapter_count = len(list_chapter_files())
    active = get_active_profile()
    skills = selected_skill_names(active_skill_ids())
    st.markdown(
        f"""
        <div class="app-hero">
          <div class="hero-layout">
            <div>
              <div class="hero-kicker">Fanqie Novel Lab · Original Fiction Studio</div>
              <div class="hero-title">把灵感整理成可连载的作品。</div>
              <div class="hero-subtitle">用公开元数据做题材观察，用创作约束控制质量，用人工审核守住原创边界。界面按真实创作流程重排：数据、题材、大纲、润色、避撞、正文、导出。</div>
              <div class="hero-actions">
                <span class="hero-chip">🍅 元数据 {books_count}</span>
                <span class="hero-chip">✍️ 大纲 {outline_count}</span>
                <span class="hero-chip">📖 章节 {chapter_count}</span>
                <span class="hero-chip">🤖 {ui_escape(active.model)}</span>
              </div>
            </div>
            <div class="hero-panel">
              <div class="hero-panel-title">当前项目</div>
              <div class="hero-stat-row">
                <div class="hero-stat"><strong>{ui_escape(current_outline_title())}</strong><span>当前大纲</span></div>
                <div class="hero-stat"><strong>{ui_escape(latest_chapter_label())}</strong><span>最近章节</span></div>
                <div class="hero-stat"><strong>{len(active_skill_ids())}</strong><span>启用约束</span></div>
                <div class="hero-stat"><strong>{chapter_count}</strong><span>章节版本</span></div>
              </div>
              <div style="margin-top:12px">{chips_html(skills, 4) or '<span class="pill">未启用约束</span>'}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, desc: str, badge: str | None = None) -> None:
    badge_html = f"<div class='page-badge'>{ui_escape(badge)}</div>" if badge else ""
    st.markdown(
        f"""
        <div class="page-head">
          <div>
            <div class="page-eyebrow">{ui_escape(eyebrow)}</div>
            <div class="page-title">{ui_escape(title)}</div>
            <div class="page-desc">{ui_escape(desc)}</div>
          </div>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_strip(items: list[tuple[str, str, str]]) -> None:
    cells = []
    for label, value, hint in items:
        cells.append(
            f'<div class="metric-item"><div class="metric-label">{ui_escape(label)}</div>'
            f'<div class="metric-value" title="{ui_escape(value)}">{ui_escape(value)}</div>'
            f'<div class="metric-hint" title="{ui_escape(hint)}">{ui_escape(hint)}</div></div>'
        )
    st.markdown('<div class="metric-bar">' + "".join(cells) + "</div>", unsafe_allow_html=True)


def empty_state(title: str, desc: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
          <strong>{ui_escape(title)}</strong>
          <span>{ui_escape(desc)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def asset_card(title: str, desc: str, ready: bool, state: str) -> None:
    cls = "asset-card ready" if ready else "asset-card"
    st.markdown(
        f"""
        <div class="{cls}">
          <div class="asset-top">
            <div class="asset-title">{ui_escape(title)}</div>
            <div class="asset-state">{ui_escape(state)}</div>
          </div>
          <div class="asset-desc">{ui_escape(desc)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def checklist_html(items: list[tuple[str, bool]]) -> str:
    rows = []
    for label, ok in items:
        rows.append(
            f"<div class=\"check-row {'ok' if ok else ''}\">"
            f"<div class=\"check-dot\">{'✓' if ok else '•'}</div>"
            f"<div>{ui_escape(label)}</div>"
            "</div>"
        )
    return '<div class="check-list">' + "".join(rows) + "</div>"


def compact_checklist_html(items: list[tuple[str, bool]]) -> str:
    return checklist_html(items).replace('class="check-list"', 'class="check-list compact"', 1)


def readiness_meter_html(score: int, label: str = "Brief 完整度") -> str:
    score = max(0, min(100, int(score)))
    return (
        '<div class="readiness-meter">'
        '<div class="readiness-top">'
        f'<div><div class="readiness-label">{ui_escape(label)}</div><div class="readiness-score">{score}%</div></div>'
        f'<div class="outline-pill">{"可生成" if score >= 70 else "待补全"}</div>'
        "</div>"
        '<div class="readiness-bar">'
        f'<div class="readiness-fill" style="width:{score}%"></div>'
        "</div>"
        "</div>"
    )


def outline_shell_html(outline: NovelOutline | None, books_count: int, history_count: int) -> str:
    desc = outline.one_line_pitch if outline else "先写核心钩子，再补题材约束；生成后进入画布审核。"
    status = "已加载" if outline else "未加载"
    return (
        '<div class="outline-shell"><div class="outline-shell-inner">'
        '<div class="outline-kicker">Outline Studio</div>'
        '<div class="outline-title">题材与大纲</div>'
        f'<div class="outline-desc">{ui_escape(desc)}</div>'
        '<div class="outline-actions">'
        f'<span class="outline-pill">✍️ {ui_escape(status)}</span>'
        f'<span class="outline-pill">🍅 样本 {books_count}</span>'
        f'<span class="outline-pill">🗂️ 历史 {history_count}</span>'
        f'<span class="outline-pill">🤖 {ui_escape(get_active_profile().model)}</span>'
        '</div>'
        '</div></div>'
    )

def outline_steps_html(active: int) -> str:
    steps = [
        ("01", "题材 Brief", "输入题材、钩子、约束"),
        ("02", "大纲画布", "看卖点、前十章、导出"),
        ("03", "版本库", "加载历史 JSON 继续"),
    ]
    html_parts = []
    for index, title, desc in steps:
        cls = "outline-step active" if int(index) == active else "outline-step"
        html_parts.append(f'<div class="{cls}"><strong>{index} {ui_escape(title)}</strong><span>{ui_escape(desc)}</span></div>')
    return '<div class="outline-steps">' + "".join(html_parts) + "</div>"


def workflow_card(icon: str, title: str, desc: str, ready: bool, state: str) -> None:
    cls = "workflow-card ready" if ready else "workflow-card"
    st.markdown(
        f"""
        <div class="{cls}">
          <div class="icon">{ui_escape(icon)}</div>
          <h3>{ui_escape(title)}</h3>
          <p>{ui_escape(desc)}</p>
          <span class="state">{ui_escape(state)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def flow_row_html(icon: str, title: str, desc: str, ready: bool, state: str) -> str:
    cls = "flow-row ready" if ready else "flow-row"
    return (
        f"<div class=\"{cls}\">"
        f"<div class=\"flow-icon\">{ui_escape(icon)}</div>"
        "<div class=\"flow-main\">"
        f"<div class=\"flow-title\">{ui_escape(title)}</div>"
        f"<div class=\"flow-desc\">{ui_escape(desc)}</div>"
        "</div>"
        f"<div class=\"flow-state\">{ui_escape(state)}</div>"
        "</div>"
    )


def flow_anchor_html(icon: str, title: str, desc: str, ready: bool, state: str, href: str) -> str:
    return f"<a class=\"flow-anchor\" href=\"{ui_escape(href)}\">{flow_row_html(icon, title, desc, ready, state)}</a>"


def creation_flow_html(steps: list[tuple[str, str, str, bool, str, str]]) -> str:
    total = max(len(steps), 1)
    done = sum(1 for step in steps if step[3])
    progress = round(done / total * 100)
    current_index = next((idx for idx, step in enumerate(steps, start=1) if not step[3]), total)
    cards = []
    for idx, (icon, title, desc, ready, state, _tab_key) in enumerate(steps, start=1):
        cls = "creation-step"
        if ready:
            cls += " ready"
        if idx == current_index:
            cls += " current"
        cards.append(
            f'<div class="{cls}">'
            '<div class="creation-step-top">'
            f'<div class="creation-step-no">{idx:02d}</div>'
            f'<div class="creation-step-icon">{ui_escape(icon)}</div>'
            "</div>"
            f'<div class="creation-step-title">{ui_escape(title)}</div>'
            f'<div class="creation-step-desc">{ui_escape(desc)}</div>'
            f'<div class="creation-step-state">{ui_escape(state)}</div>'
            "</div>"
        )
    return (
        '<div class="creation-flow">'
        '<div class="creation-flow-head">'
        '<div>'
        '<div class="section-kicker">FLOW</div>'
        '<div class="creation-flow-title">创作流程</div>'
        '<div class="creation-flow-sub">按真实创作顺序推进；下方选择步骤后只切换客户端模块，不跳浏览器路由。</div>'
        '</div>'
        '<div class="creation-flow-progress">'
        f'<div class="creation-flow-progress-label"><span>完成度</span><b>{done}/{total}</b></div>'
        f'<div class="creation-flow-bar"><div class="creation-flow-fill" style="width:{progress}%"></div></div>'
        '</div>'
        '</div>'
        '<div class="creation-flow-track">'
        + "".join(cards)
        + "</div></div>"
    )


def outline_summary(outline: NovelOutline | None) -> dict[str, str]:
    if not outline:
        return {"标题": "未加载", "一句话": "暂无", "题材": "暂无", "主角": "暂无"}
    protagonist = outline.protagonist or {}
    protagonist_name = protagonist.get("name") or protagonist.get("姓名") or protagonist.get("role") or "已设置"
    return {
        "标题": outline.title_candidates[0] if outline.title_candidates else "未命名大纲",
        "一句话": outline.one_line_pitch,
        "题材": outline.genre_positioning,
        "主角": str(protagonist_name),
    }


def render_outline_snapshot(outline: NovelOutline | None) -> None:
    if not outline:
        empty_state("还没有当前大纲", "生成或加载大纲后，这里会展示项目摘要。")
        return
    summary = outline_summary(outline)
    st.markdown(
        f"""
        <div class="info-card">
          <h4>✍️ {ui_escape(summary['标题'])}</h4>
          <p>{ui_escape(clip_text(summary['一句话'], 220))}</p>
          <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
            <span class="pill">{ui_escape(summary['题材'])}</span>
            <span class="pill">主角：{ui_escape(summary['主角'])}</span>
            <span class="pill">卖点 {len(outline.selling_points)}</span>
            <span class="pill">前10章 {len(outline.first_10_chapters)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def current_outline_title() -> str:
    outline = normalize_outline(st.session_state.get("outline"))
    if not outline:
        return "未加载"
    return outline.title_candidates[0] if outline.title_candidates else "未命名大纲"


def latest_chapter_label() -> str:
    chapter = normalize_chapter(st.session_state.get("chapter_draft") or st.session_state.get("edit_chapter"))
    if not chapter:
        return "未生成"
    return f"第 {chapter.chapter_no} 章"


@st.dialog("模型设置", width="large")
def model_settings_dialog() -> None:
    active = get_active_profile()
    seed = f"{active.name}|{active.provider}|{active.base_url}|{active.model}"
    if st.session_state.get("_model_dialog_seed") != seed:
        st.session_state["_model_dialog_seed"] = seed
        st.session_state["model_provider_kind"] = "Claude CLI" if active.provider == "claude_cli" else "OpenAI-compatible"
        st.session_state["model_profile_name"] = active.name if active.name != "default" else ""
        st.session_state["model_openai_base_url"] = "" if active.provider == "claude_cli" else active.base_url
        st.session_state["model_openai_api_key"] = "" if active.provider == "claude_cli" else active.api_key
        st.session_state["model_openai_model_name"] = "" if active.provider == "claude_cli" else active.model
        st.session_state["model_claude_cli_model"] = active.model if active.provider == "claude_cli" else "mimo-v2.5-pro"
        st.session_state["model_profile_note"] = active.note
        st.session_state["model_temperature"] = float(active.temperature)
        st.session_state["model_timeout"] = int(active.timeout_seconds)
        st.session_state.pop("fetched_models", None)

    st.caption("开放配置：任意 OpenAI-compatible 中转站、聚合网关、本地模型服务，或本机 Claude CLI。只保存到本地配置文件。")
    provider_label = st.segmented_control(
        "Provider",
        ["OpenAI-compatible", "Claude CLI"],
        default="Claude CLI" if active.provider == "claude_cli" else "OpenAI-compatible",
        key="model_provider_kind",
        width="stretch",
    ) or "OpenAI-compatible"
    provider = "claude_cli" if provider_label == "Claude CLI" else "openai"
    fallback_name = "claude-mimo" if provider == "claude_cli" else "custom-relay"
    profile_name = st.text_input("配置名", placeholder=f"例如：{fallback_name} / openrouter-claude / local-qwen", key="model_profile_name")
    temperature = st.slider("Temperature", 0.0, 1.5, float(active.temperature), 0.05, key="model_temperature")
    timeout_seconds = st.number_input("超时秒数", min_value=10, max_value=900, value=int(active.timeout_seconds), step=10, key="model_timeout", help="大纲和长章节建议 180 秒以上；本地模型可按机器性能调高。")

    if provider == "claude_cli":
        base_url = "claude-cli://local"
        api_key = ""
        st.text_input("Base URL", value=base_url, disabled=True, key="model_claude_base_url", help="Claude CLI 走本机命令，不需要 HTTP Base URL。")
        selected_model = st.text_input(
            "Claude CLI 模型名",
            placeholder="例如：mimo-v2.5-pro / opus / sonnet",
            key="model_claude_cli_model",
        )
        st.markdown(
            "<div class='soft-note'>保存后生成大纲、润色和正文都会通过本机 <code>claude -p --model ...</code> 调用。请确认终端里可以直接运行 Claude CLI。</div>",
            unsafe_allow_html=True,
        )
    else:
        preset = st.selectbox("中转/供应商预设", list(PRESET_BASE_URLS.keys()), key="model_preset", help="预设只负责快速填 URL；保存时不会限制模型名。")
        preset_url = PRESET_BASE_URLS.get(preset, "")
        if preset_url:
            if st.button(f"填入预设地址：{preset}", width="stretch", key="model_apply_preset_url"):
                st.session_state["model_openai_base_url"] = preset_url
                st.session_state.pop("fetched_models", None)
                st.rerun()
        base_url = st.text_input(
            "Base URL",
            placeholder="https://你的中转域名/v1 或 http://127.0.0.1:3000/v1",
            key="model_openai_base_url",
            help="支持 One API/New API、OpenRouter、LiteLLM、Ollama、LM Studio、vLLM 等 OpenAI-compatible 接口。",
        )
        api_key = st.text_input(
            "API Key",
            placeholder="按中转站要求填写；本地服务、内网无鉴权代理可留空",
            type="password",
            key="model_openai_api_key",
        )
        if st.button("测试连接并读取模型列表", width="stretch", key="model_fetch_models"):
            try:
                models = fetch_models(base_url=base_url, api_key=api_key, timeout_seconds=int(timeout_seconds))
                st.session_state["fetched_models"] = models
                st.success(f"获取到 {len(models)} 个模型" if models else "接口可访问，但没有返回模型。")
            except Exception as exc:
                st.error(f"获取失败：{exc}")
        fetched = st.session_state.get("fetched_models") or []
        selected_from_list = (
            st.selectbox("接口返回模型", ["手动填写"] + fetched, index=0, key="model_fetched_select")
            if fetched
            else "手动填写"
        )
        manual_model = st.text_input(
            "模型名",
            placeholder="任意模型 ID，例如：gpt-4o / claude-3.7-sonnet / deepseek-chat / qwen-plus / llama3.1",
            key="model_openai_model_name",
        )
        selected_model = selected_from_list if selected_from_list != "手动填写" else manual_model
        st.markdown(
            "<div class='soft-note'>模型名永远允许手动填写；模型列表只是辅助选择。中转站返回不了模型列表也不影响保存。</div>",
            unsafe_allow_html=True,
        )
    note = st.text_area(
        "配置备注",
        placeholder="例如：用于大纲生成 / 长上下文模型 / 本地测试 / 成本较低的正文模型",
        height=78,
        key="model_profile_note",
    )

    if st.button("保存并切换到该模型", type="primary", width="stretch", key="model_save_profile"):
        if provider != "claude_cli" and not base_url.strip():
            st.error("请填写 Base URL。")
            return
        if not selected_model.strip():
            st.error("请填写模型名。")
            return
        profile_name_value = profile_name.strip() or fallback_name
        if provider != active.provider and profile_name_value == active.name:
            profile_name_value = fallback_name
        note_value = note.strip()
        if provider != active.provider and note_value == (active.note or "").strip():
            note_value = ""
        profile = ModelProfile(
            name=profile_name_value,
            provider=provider,
            base_url=base_url.strip(),
            api_key=api_key.strip(),
            model=selected_model.strip(),
            temperature=float(temperature),
            timeout_seconds=int(timeout_seconds),
            note=note_value,
        )
        upsert_profile(profile, make_active=True)
        st.success(f"模型配置已保存并切换：{profile.name} · {profile.model}")
        st.rerun()


@st.dialog("加载历史大纲", width="large")
def load_outline_dialog() -> None:
    files = saved_outline_files()
    if not files:
        st.warning("暂无已保存大纲。")
        return
    labels = [p.name for p in files]
    name = st.selectbox("选择大纲 JSON", labels)
    path = files[labels.index(name)]
    with st.expander("预览", expanded=False):
        try:
            outline = load_outline_from_path(path)
            st.markdown(outline_to_markdown(outline)[:6000])
        except Exception as exc:
            st.error(f"预览失败：{exc}")
    if st.button("加载到当前项目", type="primary", width="stretch"):
        try:
            st.session_state["outline"] = load_outline_from_path(path)
            st.session_state["outline_saved_json"] = str(path)
            st.success(f"已加载：{path.name}")
            st.rerun()
        except Exception as exc:
            st.error(f"加载失败：{exc}")


@st.dialog("创作约束库", width="large")
def skills_dialog() -> None:
    if "selected_writing_skill_ids" not in st.session_state:
        st.session_state["selected_writing_skill_ids"] = DEFAULT_WRITING_SKILL_IDS
    labels = [skill_label(s) for s in ALL_WRITING_SKILLS]
    label_to_id = {skill_label(s): s.id for s in ALL_WRITING_SKILLS}
    default_labels = [skill_label(s) for s in ALL_WRITING_SKILLS if s.id in st.session_state["selected_writing_skill_ids"]]
    chosen = st.multiselect("启用技能约束", labels, default=default_labels)
    chosen_ids = [label_to_id[x] for x in chosen]
    st.markdown("#### 约束预览")
    preview_tab1, preview_tab2, preview_tab3 = st.tabs(["大纲", "正文", "避撞"])
    with preview_tab1:
        st.text(format_skill_constraints(chosen_ids, "outline") or "未启用")
    with preview_tab2:
        st.text(format_skill_constraints(chosen_ids, "chapter") or "未启用")
    with preview_tab3:
        st.text(format_skill_constraints(chosen_ids, "avoid") or "未启用")
    if st.button("保存创作约束", type="primary", width="stretch"):
        st.session_state["selected_writing_skill_ids"] = chosen_ids
        st.success("创作约束已保存")
        st.rerun()


@st.dialog("加载章节到编辑器", width="large")
def load_chapter_dialog() -> None:
    files = list_chapter_files()
    if not files:
        st.warning("暂无已保存章节。")
        return
    labels = [p.name for p in files]
    name = st.selectbox("选择章节 JSON", labels)
    path = files[labels.index(name)]
    if st.button("加载到章节编辑器", type="primary", width="stretch"):
        try:
            st.session_state["edit_chapter"] = load_chapter_from_path(path)
            st.session_state["edit_chapter_source"] = str(path)
            st.session_state["edit_chapter_version"] = st.session_state.get("edit_chapter_version", 0) + 1
            st.success(f"已加载：{path.name}")
            st.rerun()
        except Exception as exc:
            st.error(f"加载失败：{exc}")


APP_TABS = [
    ("home", "工作台"),
    ("data", "数据"),
    ("outline", "大纲"),
    ("review", "润色"),
    ("collision", "避撞"),
    ("chapter", "章节"),
    ("publish", "发布"),
    ("export", "导出"),
    ("settings", "项目设置"),
]
TAB_LABEL_TO_KEY = {label: key for key, label in APP_TABS}
TAB_KEY_TO_LABEL = {key: label for key, label in APP_TABS}


def set_app_tab(tab_key: str) -> None:
    st.session_state["app_tab"] = tab_key


def nav_button(tab_key: str, label: str, icon: str = "", *, key: str | None = None) -> None:
    button_label = f"{icon} {label}".strip()
    if st.button(button_label, width="stretch", key=key or f"nav_{tab_key}_{abs(hash(label))}"):
        # Do not mutate the segmented-control widget key after it has already
        # been instantiated in this run. Store a pending target and sync it at
        # the very top of the next rerun; this keeps module tabs in the same
        # Streamlit page instead of bouncing back to the previous route/value.
        st.session_state["pending_app_tab"] = tab_key
        st.rerun()


def render_sidebar_tools() -> None:
    active = get_active_profile()
    pending_tab = st.session_state.pop("pending_app_tab", None)
    if pending_tab in TAB_KEY_TO_LABEL:
        st.session_state["app_tab"] = pending_tab
        st.session_state["app_tab_segmented"] = TAB_KEY_TO_LABEL[pending_tab]
    if "app_tab" not in st.session_state:
        st.session_state["app_tab"] = "outline"
    if "app_tab_segmented" not in st.session_state:
        st.session_state["app_tab_segmented"] = TAB_KEY_TO_LABEL.get(st.session_state["app_tab"], "大纲")
    current_key = st.session_state.get("app_tab", "outline")
    current_label = TAB_KEY_TO_LABEL.get(current_key, "大纲")

    st.markdown(
        f"""
        <div class="top-nav">
          <div class="top-brand">
            <div class="top-logo">F</div>
            <div>
              <div class="top-title">Fanqie Novel Lab</div>
              <div class="top-sub">{ui_escape(current_outline_title())} · {ui_escape(latest_chapter_label())} · {len(active_skill_ids())} 个约束</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_label = st.segmented_control(
        "模块",
        [label for _, label in APP_TABS],
        default=current_label,
        key="app_tab_segmented",
        label_visibility="collapsed",
    ) or current_label
    selected_key = TAB_LABEL_TO_KEY.get(selected_label, "outline")
    if selected_key != current_key:
        set_app_tab(selected_key)
        st.rerun()

    st.markdown(
        f"""
        <div class="top-meta">
          <span class="pill">🤖 {ui_escape(active.model)}</span>
          <span class="pill">Provider: {ui_escape(active.provider)}</span>
          <span class="pill">当前：{ui_escape(selected_label)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_home() -> None:
    render_hero()
    books_count = len(list_books(limit=10_000))
    outlines = saved_outline_files()
    chapters = list_chapter_files()
    outline = normalize_outline(st.session_state.get("outline"))
    chapter = normalize_chapter(st.session_state.get("chapter_draft") or st.session_state.get("edit_chapter"))
    findings = st.session_state.get("collision_findings")

    stat_strip(
        [
            ("当前大纲", current_outline_title(), "项目主线"),
            ("最近章节", latest_chapter_label(), "正文进度"),
            ("模型", get_active_profile().model, "一键切换"),
            ("样本", str(books_count), "公开元数据"),
        ]
    )
    st.markdown('<div class="editor-section">', unsafe_allow_html=True)
    steps = [
        ("🍅", "数据花园", "采集/导入公开元数据", books_count > 0, f"{books_count} 条样本" if books_count else "待采集", "data"),
        ("✍️", "题材与大纲", "设定题材并生成原创蓝图", outline is not None, "已有大纲" if outline else "待生成", "outline"),
        ("🪶", "人审润色", "按主编标准改大纲", outline is not None, "可润色" if outline else "等待大纲", "review"),
        ("🛡️", "避撞审查", "对比本地公开元数据", findings is not None, "已审查" if findings is not None else "待审查", "collision"),
        ("📖", "章节工坊", "按章数和字数生成正文", chapter is not None, "已有章节" if chapter else "待生成", "chapter"),
    ]
    st.markdown(creation_flow_html(steps), unsafe_allow_html=True)
    flow_labels = [f"{icon} {title}" for icon, title, *_rest in steps]
    flow_label_to_tab = {f"{icon} {title}": tab_key for icon, title, _desc, _ready, _state, tab_key in steps}
    nav_version = int(st.session_state.get("home_flow_nav_version", 0))
    picked_flow = st.segmented_control(
        "进入流程步骤",
        flow_labels,
        default=None,
        key=f"home_flow_jump_{nav_version}",
        label_visibility="collapsed",
        width="stretch",
    )
    st.markdown("<div class='flow-jump-caption'>选择一个步骤即可进入对应模块。</div>", unsafe_allow_html=True)
    if picked_flow:
        st.session_state["home_flow_nav_version"] = nav_version + 1
        st.session_state["pending_app_tab"] = flow_label_to_tab[picked_flow]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="editor-section">', unsafe_allow_html=True)
    section_intro("NOW", "当前项目快照", "不显示假数据，只显示本地会话里已有的内容。")
    render_outline_snapshot(outline)
    if chapter:
        info_card(
            f"第 {chapter.chapter_no} 章 · {chapter.title}",
            f"当前正文长度 {content_length(chapter.content)} 字；目标 {chapter.target_words or '未指定'} 字。",
            icon="📖",
        )
    else:
        empty_state("暂无章节", "生成正文后会在这里显示最近章节。")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="editor-section">', unsafe_allow_html=True)
    section_intro("RECENT", "最近输出", "直接读取 outputs 目录。")
    tab_o, tab_c = st.tabs(["大纲", "章节"])
    with tab_o:
        rows = file_table(outlines, 6)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
            render_history_delete_panel(outlines, key_prefix="home_outline", allowed_dir=OUTLINE_DIR, item_label="大纲")
        else:
            st.caption("暂无大纲文件。")
    with tab_c:
        rows = file_table(chapters, 6)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
            render_history_delete_panel(chapters, key_prefix="home_chapter", allowed_dir=CHAPTER_DIR, item_label="章节")
        else:
            st.caption("暂无章节文件。")
    st.markdown('</div>', unsafe_allow_html=True)

def render_data_page() -> None:
    books_snapshot = list_books(limit=10_000)
    categories_local = sorted({b.category for b in books_snapshot if b.category})
    max_heat = int(max([b.heat or 0 for b in books_snapshot], default=0))
    page_header(
        "DATA GARDEN",
        "🍅 数据花园",
        "采集和管理公开元数据，用于趋势分析、题材观察和避撞审查。这里只处理公开元数据，不处理正文。",
        "公开元数据 · 非正文",
    )
    stat_strip(
        [
            ("样本总数", str(len(books_snapshot)), "本地 SQLite"),
            ("分类数量", str(len(categories_local)), "已覆盖题材"),
            ("最高热度", str(max_heat), "公开榜单热度"),
            ("最近分类", categories_local[0] if categories_local else "暂无", "可继续扩充"),
        ]
    )

    tab_source, tab_library, tab_distribution, tab_db = st.tabs(["采集", "样本库", "分布", "数据库"])
    with tab_source:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("SOURCE", "选择数据来源", "优先使用公开榜单 API；CSV 用于导入你自己的合规元数据。")
        source_mode = st.segmented_control(
            "数据来源",
            ["榜单 API", "CSV 导入", "公开 URL"],
            default="榜单 API",
            key="data_source_mode",
            label_visibility="collapsed",
        ) or "榜单 API"

        if source_mode == "榜单 API":
            try:
                remote_categories = cached_rank_categories()
            except Exception as exc:
                remote_categories = []
                st.warning(f"分类获取失败，可手动填写分类 ID：{exc}")
            with st.form("rank_crawl_form"):
                if remote_categories:
                    labels = [f"{c['gender_name']} · {c['name']} · {c['id']}" for c in remote_categories]
                    label = st.selectbox("分类", labels, index=next((i for i, x in enumerate(labels) if "都市脑洞" in x), 0))
                    selected_cat = remote_categories[labels.index(label)]
                    category_id = selected_cat["id"]
                    gender = int(selected_cat["gender"])
                else:
                    category_id = st.text_input("分类 ID", value="262", placeholder="番茄分类 ID，例如 262")
                    gender = st.selectbox("频道", [1, 0], format_func=lambda x: "男频" if x == 1 else "女频")
                rank_mold = st.selectbox("榜单", [1, 2], format_func=lambda x: "阅读榜" if x == 1 else "新书榜")
                limit = st.slider("条数", min_value=10, max_value=200, value=50, step=10)
                submit = st.form_submit_button("采集榜单元数据", type="primary", width="stretch")
            if submit:
                try:
                    books = crawl_rank_api(category_id=str(category_id), gender=int(gender), rank_mold=int(rank_mold), limit=int(limit))
                    count = upsert_books(books)
                    st.success(f"采集并保存 {count} 条真实公开元数据")
                    st.rerun()
                except Exception as exc:
                    st.error(f"采集失败：{exc}")

        elif source_mode == "CSV 导入":
            uploaded = st.file_uploader("上传 CSV", type=["csv"], key="metadata_csv_upload", help="用于导入你自己整理的公开元数据表，不导入正文。")
            st.caption("字段可参考 sample_data/fanqie_metadata_template.csv。")
            if uploaded:
                df = pd.read_csv(uploaded)
                st.dataframe(df.head(12), width="stretch", hide_index=True)
                if st.button("导入 CSV 元数据", type="primary", width="stretch", key="import_csv_button"):
                    books = books_from_dataframe(df)
                    count = upsert_books(books)
                    st.success(f"已导入/更新 {count} 条元数据")
                    st.rerun()

        else:
            with st.form("url_crawl_form"):
                url = st.text_input("公开榜单/分类页 URL", value="https://fanqienovel.com/rank/1_1_262", placeholder="https://fanqienovel.com/rank/...")
                url_limit = st.slider("URL 最多采集", min_value=10, max_value=200, value=50, step=10)
                submit_url = st.form_submit_button("采集 URL 元数据", type="primary", width="stretch")
            if submit_url:
                try:
                    books = crawl_public_metadata(url, limit=url_limit)
                    count = upsert_books(books)
                    st.success(f"采集并保存 {count} 条")
                    if not books:
                        st.warning("未解析到数据。页面可能为动态渲染，可改用榜单 API 或 CSV 导入。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"采集失败：{exc}")

        with st.expander("采集合规线", expanded=False):
            st.write("不登录、不绕验证码、不抓付费或正文，只保存公开榜单/简介/标签等元数据。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_library:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("LIBRARY", "本地样本库", "可以筛选、预览、清空本地 SQLite；不会删除 outputs 里的大纲和章节。")
        if books_snapshot:
            selected_category = st.selectbox("分类筛选", ["全部"] + categories_local, key="data_category_filter", help="只筛选本地 SQLite 中已保存的元数据。")
            preview_limit = st.selectbox("显示条数", [50, 100, 200, 500], index=2, key="data_preview_limit")
            recent_books = list_books(limit=int(preview_limit), category=None if selected_category == "全部" else selected_category)
            rows = books_table_rows(recent_books)
            st.dataframe(rows, width="stretch", hide_index=True)
            csv_data = pd.DataFrame(books_table_rows(books_snapshot)).to_csv(index=False).encode("utf-8-sig")
            st.download_button("导出当前元数据 CSV", data=csv_data, file_name="fanqie_metadata_export.csv", mime="text/csv", width="stretch")
            with st.expander("危险操作：清空本地元数据表", expanded=False):
                confirm_clear = st.checkbox("我确认只清空 SQLite 里的 books 元数据，不删除大纲、章节和发布包", key="clear_books_confirm")
                if st.button("清空本地元数据表", width="stretch", key="clear_books_button", disabled=not confirm_clear):
                    deleted = clear_books(only_sample=False)
                    st.warning(f"已清空 {deleted} 条元数据")
                    st.rerun()
        else:
            empty_state("暂无真实数据", "先在“采集”页抓取公开榜单，或导入你自己的 CSV 元数据。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_distribution:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("DISTRIBUTION", "分类分布", "基于本地样本实时统计。")
        if books_snapshot and categories_local:
            df = pd.DataFrame([{"分类": b.category or "未分类", "数量": 1} for b in books_snapshot])
            chart_df = df.groupby("分类", as_index=False)["数量"].sum().sort_values("数量", ascending=False).head(20)
            st.bar_chart(chart_df.set_index("分类"))
        else:
            st.caption("暂无可统计分类。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_db:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("DATABASE", "本地数据库", "SQLite、配置文件、输出目录都在本机；这里给出可核对的真实路径和文件数量。")
        st.dataframe(database_status_rows(), width="stretch", hide_index=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.dataframe(output_status_rows(), width="stretch", hide_index=True)
        settings = get_settings()
        if settings.db_path.exists():
            st.download_button("下载 SQLite 备份", data=settings.db_path.read_bytes(), file_name=settings.db_path.name, mime="application/octet-stream", width="stretch")
        st.markdown(f"<div class='code-path'>项目根目录：{ui_escape(OUTPUT_DIR.parent)}</div>", unsafe_allow_html=True)
        if st.button("重新读取数据库状态", width="stretch", key="refresh_db_status"):
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def render_outline_page() -> None:
    outline = normalize_outline(st.session_state.get("outline"))
    books_count = len(list_books(limit=10_000))
    history_count = len(saved_outline_files())

    st.markdown(outline_shell_html(outline, books_count, history_count), unsafe_allow_html=True)

    tab_brief, tab_canvas, tab_history = st.tabs(["Brief", "画布", "版本"])

    with tab_brief:
        genre_value = str(st.session_state.get("outline_genre", "都市脑洞")).strip()
        hook_value = str(st.session_state.get("outline_core_hook", "")).strip()
        style_value = str(st.session_state.get("outline_style", "")).strip()
        ready_items = [
            ("题材", bool(genre_value)),
            ("核心钩子", bool(hook_value)),
            ("风格", bool(style_value)),
            ("元数据", books_count > 0),
            ("约束", len(active_skill_ids()) > 0),
        ]
        ready_score = round(sum(1 for _, ok in ready_items if ok) / len(ready_items) * 100)

        st.markdown(outline_steps_html(1), unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="editor-section">
              <div class="editor-section-head">
                <div>
                  <div class="section-kicker">STATUS</div>
                  <div class="editor-section-title">生成状态</div>
                  <div class="editor-section-desc">状态只做提示，不打断写作。缺少样本也可以继续生成。</div>
                </div>
              </div>
              <div class="editor-status-strip">
                <div class="editor-status-item"><b>{ui_escape(current_outline_title())}</b><span>当前大纲</span></div>
                <div class="editor-status-item"><b>{books_count}</b><span>元数据样本</span></div>
                <div class="editor-status-item"><b>{history_count}</b><span>历史版本</span></div>
                <div class="editor-status-item"><b>{len(active_skill_ids())}</b><span>创作约束</span></div>
                <div class="editor-status-item"><b>{ready_score}%</b><span>Brief 完整度</span></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("BRIEF", "创作输入", "单栏输入，核心内容优先；篇幅和禁忌放到高级设置。")
        with st.form("outline_form_single_column"):
            genre = st.text_input("题材", value="都市脑洞", placeholder="例如：都市脑洞 / 玄幻升级 / 悬疑灵异 / 古言权谋", key="outline_genre")
            audience = st.text_input("读者", value="男频", placeholder="例如：男频 18-35 / 女频情感 / 都市爽文读者", key="outline_audience")
            core_hook = st.text_area(
                "核心钩子",
                value="底层主角能看到他人的隐藏信息，但每次使用都会消耗自身重要记忆。",
                placeholder="写清主角、能力、代价、第一章冲突：谁想要什么，马上会失去什么？",
                height=92,
                key="outline_core_hook",
            )
            style = st.text_area("风格要求", value="爽文、节奏快、三章内出爆点、每章结尾有钩子", placeholder="节奏、文风、禁忌、章节钩子、平台适配要求", height=72, key="outline_style")
            with st.expander("高级设置：篇幅、必含、禁忌", expanded=False):
                target_words = st.number_input("目标字数", min_value=100_000, max_value=5_000_000, value=1_000_000, step=100_000, key="outline_target_words")
                target_chapters = st.number_input("目标章节", min_value=30, max_value=1500, value=300, step=10, key="outline_target_chapters")
                must_have_text = st.text_area("必须包含", value="强开局\n持续升级\n阶段性反派\n现实压力", placeholder="一行一个：必备桥段、人物关系、世界规则", height=100, key="outline_must_have")
                avoid_text = st.text_area("避免事项", value="避免同质化开局\n避免无代价开挂\n避免人物工具化\n避免节奏拖沓", placeholder="一行一个：不要写的套路、雷点、撞文风险", height=100, key="outline_avoid")
            submit = st.form_submit_button("生成原创大纲", type="primary", width="stretch")
        if submit:
            try:
                source_books = list_books(limit=100, category=genre)
                if not source_books:
                    st.warning("当前题材暂无元数据样本：本次只基于你的 Brief 与约束生成，不展示伪趋势。")
                trend = analyze_trends(genre, source_books)
                outline_skill_text = active_skill_constraints("outline")
                avoid_skill_text = active_skill_constraints("avoid")
                topic = TopicBrief(
                    genre=genre.strip(),
                    audience=audience.strip(),
                    core_hook=core_hook.strip(),
                    style=inject_skill_text(style, "outline"),
                    target_words=int(target_words),
                    target_chapters=int(target_chapters),
                    must_have=[x.strip() for x in must_have_text.splitlines() if x.strip()] + ([outline_skill_text] if outline_skill_text else []),
                    avoid=[x.strip() for x in avoid_text.splitlines() if x.strip()] + ([avoid_skill_text] if avoid_skill_text else []),
                )
                new_outline = generate_outline(topic, trend)
                json_path, md_path, outline_id = save_outline_files(new_outline, genre)
                st.session_state["trend"] = trend
                st.session_state["outline"] = new_outline
                st.session_state["outline_saved_json"] = str(json_path)
                st.session_state["outline_saved_md"] = str(md_path)
                st.success(f"已生成并保存 #{outline_id}: {json_path.name}")
                nav_button("review", "进入人审润色", "🪶", key="nav_outline_to_review_generated")
            except Exception as exc:
                st.error(f"生成失败：{exc}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("CHECK", "生成前检查", "轻量提示，只保留必要的生成前状态。")
        st.markdown(readiness_meter_html(ready_score), unsafe_allow_html=True)
        st.markdown(compact_checklist_html([(f"{name}已就绪", ok) for name, ok in ready_items]), unsafe_allow_html=True)
        constraints = selected_skill_names(active_skill_ids())
        if constraints:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(chips_html(constraints, 8), unsafe_allow_html=True)
        with st.popover("查看详细约束", width="stretch"):
            st.text(active_skill_constraints("outline") or "未启用大纲约束")
            st.text(active_skill_constraints("avoid") or "未启用避撞约束")
        if outline:
            nav_button("review", "审稿润色", "🪶", key="nav_outline_check_review")
        else:
            if st.button("打开历史大纲库", key="outline_load_history_single", width="stretch"):
                load_outline_dialog()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_canvas:
        st.markdown(outline_steps_html(2), unsafe_allow_html=True)
        current = normalize_outline(st.session_state.get("outline"))
        if not current:
            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            empty_state("画布为空", "先在 Brief 页生成大纲，或从历史版本加载。")
            nav_button("data", "补充元数据", "🍅", key="nav_outline_to_data")
            if st.button("打开历史大纲库", key="outline_load_history_canvas", width="stretch"):
                load_outline_dialog()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("CANVAS", "大纲摘要", "先看可决策信息：一句话、卖点、人物、前十章。")
            render_outline_snapshot(current)
            st.markdown("##### 卖点")
            st.markdown(chips_html(current.selling_points, 8), unsafe_allow_html=True)
            st.markdown("##### 前五章")
            mini_rows = []
            for item in current.first_10_chapters[:5]:
                no = str(item.get("chapter") or item.get("章节") or "-")
                title = str(item.get("title") or item.get("标题") or "未命名")
                goal = clip_text(str(item.get("goal") or item.get("目标") or item.get("conflict") or ""), 72)
                mini_rows.append(f'<div class="outline-mini-row"><div class="outline-mini-no">{ui_escape(no)}</div><div><div class="outline-mini-title">{ui_escape(title)}</div><div class="outline-mini-desc">{ui_escape(goal)}</div></div></div>')
            st.markdown('<div class="outline-mini-list">' + "".join(mini_rows) + '</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("ACTIONS", "下一步", "集中放置后续操作，保持当前页面不跳转。")
            nav_button("review", "人审润色", "🪶", key="nav_outline_to_review")
            nav_button("collision", "避撞审查", "🛡️", key="nav_outline_to_collision")
            nav_button("chapter", "生成正文", "📖", key="nav_outline_to_chapter")
            md = outline_to_markdown(current)
            st.download_button("下载 Markdown", data=md, file_name="outline.md", mime="text/markdown", width="stretch")
            st.download_button("下载 JSON", data=json.dumps(current.model_dump(), ensure_ascii=False, indent=2), file_name="outline.json", mime="application/json", width="stretch")
            if st.session_state.get("outline_saved_json"):
                st.markdown(f"<div class='code-path'>{ui_escape(st.session_state['outline_saved_json'])}</div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            with st.expander("完整 Markdown 大纲", expanded=False):
                st.markdown(outline_to_markdown(current))
            if st.session_state.get("trend"):
                with st.expander("趋势输入", expanded=False):
                    st.json(st.session_state["trend"].model_dump())

    with tab_history:
        st.markdown(outline_steps_html(3), unsafe_allow_html=True)
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("LIBRARY", "历史版本", "读取 outputs/outlines；选择一个版本回到画布继续。")
        if st.button("打开历史版本库", width="stretch", key="outline_open_history_dialog_single"):
            load_outline_dialog()
        st.caption("历史 JSON/Markdown 默认只保存在本地 outputs 目录。")
        rows = file_table(saved_outline_files(), 60)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
            render_history_delete_panel(saved_outline_files(), key_prefix="outline_history", allowed_dir=OUTLINE_DIR, item_label="大纲")
        else:
            empty_state("暂无历史大纲", "生成第一个大纲后这里会出现版本列表。")
        st.markdown('</div>', unsafe_allow_html=True)

def render_review_page() -> None:
    outline = normalize_outline(st.session_state.get("outline"))
    page_header(
        "EDITOR REVIEW",
        "🪶 人审润色",
        "先像主编一样打分和写批注，再进入预览确认；所有内容在同页 tabs 内完成。",
        "人工先行",
    )
    stat_strip(
        [
            ("当前大纲", current_outline_title(), "待审对象"),
            ("启用约束", str(len(active_skill_ids())), "润色规则"),
            ("保存文件", "已自动" if st.session_state.get("outline_saved_json") else "未保存", "输出状态"),
            ("下一步", "避撞审查", "审稿后执行"),
        ]
    )
    if not outline:
        empty_state("没有可润色的大纲", "请先生成大纲，或从历史大纲加载一个项目。")
        nav_button("outline", "去题材与大纲", "✍️", key="nav_review_to_outline")
        return

    tab_desk, tab_preview = st.tabs(["控制台", "预览"])
    with tab_desk:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("REVIEW DESK", "审稿控制台", "分数用于给模型建立改稿优先级；批注越具体，润色越稳定。")
        selected_modes = st.multiselect(
            "润色方向",
            POLISH_MODES,
            default=["加强前三章爆点", "强化主角动机", "金手指规则与代价", "降低 AI 味"],
            key="review_polish_modes",
        )
        originality_score = st.slider("原创性", 1, 10, 7, key="review_originality")
        hook_score = st.slider("钩子强度", 1, 10, 7, key="review_hook")
        pacing_score = st.slider("节奏", 1, 10, 7, key="review_pacing")
        platform_fit_score = st.slider("平台适配", 1, 10, 7, key="review_platform_fit")
        character_score = st.slider("人物代入", 1, 10, 7, key="review_character")
        avg_score = round((originality_score + hook_score + pacing_score + platform_fit_score + character_score) / 5, 1)
        st.markdown(
            f"""
            <div class="soft-note">
              当前审稿均分：<b>{avg_score}/10</b>；低分项会在润色提示里被优先修正。
            </div>
            """,
            unsafe_allow_html=True,
        )
        notes = st.text_area("你的修改意见", value="主角动机再强一点，前三章冲突更狠，金手指限制更清晰。", placeholder="像主编批注一样写：哪里弱、为什么弱、要改成什么效果", height=150, key="review_notes")
        with st.expander("本次注入的润色约束", expanded=False):
            st.text(active_skill_constraints("polish") or "未启用")
        if st.button("根据审核意见润色大纲", type="primary", width="stretch", key="polish_outline_button"):
            try:
                review = OutlineReview(
                    originality_score=originality_score,
                    hook_score=hook_score,
                    pacing_score=pacing_score,
                    platform_fit_score=platform_fit_score,
                    character_score=character_score,
                    reviewer_notes=inject_skill_text(notes, "polish"),
                    polish_modes=selected_modes,
                )
                polished = polish_outline(outline, review)
                json_path, md_path, outline_id = save_outline_files(polished, genre="polished")
                st.session_state["outline"] = polished
                st.session_state["outline_saved_json"] = str(json_path)
                st.session_state["outline_saved_md"] = str(md_path)
                st.success(f"润色完成并保存 #{outline_id}: {json_path.name}")
                nav_button("collision", "下一步：避撞审查", "🛡️", key="nav_review_to_collision")
            except Exception as exc:
                st.error(f"润色失败：{exc}")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_preview:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("MANUSCRIPT", "大纲预览", "润色前后都在这里看，不再把编辑按钮和正文混在一起。")
        latest = normalize_outline(st.session_state.get("outline")) or outline
        render_outline_snapshot(latest)
        tab_md, tab_points, tab_risks = st.tabs(["Markdown", "卖点", "风险"])
        with tab_md:
            st.markdown(outline_to_markdown(latest))
        with tab_points:
            for item in latest.selling_points:
                st.markdown(f"- {item}")
        with tab_risks:
            for item in latest.risk_notes:
                st.markdown(f"- {item}")
        st.markdown('</div>', unsafe_allow_html=True)


def render_collision_page() -> None:
    findings = st.session_state.get("collision_findings")
    page_header(
        "ORIGINALITY GUARD",
        "🛡️ 避撞审查",
        "对照本地样本检查相似钩子，输出可执行修改建议。",
        "原创检查",
    )
    sample_total = len(list_books(limit=10_000))
    stat_strip(
        [
            ("当前大纲", current_outline_title(), "审查对象"),
            ("对比样本", str(sample_total), "公开元数据"),
            ("上次风险", str(len(findings)) if findings is not None else "未审查", "命中数量"),
            ("报告目录", "outputs/reviews", "Markdown"),
        ]
    )

    tab_scan, tab_report = st.tabs(["审查", "报告"])
    with tab_scan:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("SCAN", "审查设置", "选择审查对象和对比样本范围。")
        source_mode = st.segmented_control(
            "审查对象",
            ["当前大纲", "上传 JSON", "粘贴文本"],
            default="当前大纲",
            key="collision_source_mode",
        ) or "当前大纲"
        review_outline = None
        outline_name = "当前大纲"
        if source_mode == "当前大纲":
            review_outline = normalize_outline(st.session_state.get("outline"))
            if not review_outline:
                st.warning("当前未加载大纲。")
                nav_button("outline", "去生成或加载大纲", "✍️", key="nav_collision_to_outline")
        elif source_mode == "上传 JSON":
            uploaded = st.file_uploader("上传大纲 JSON", type=["json"], key="collision_json_upload")
            if uploaded:
                try:
                    review_outline = NovelOutline(**json.loads(uploaded.read().decode("utf-8")))
                    outline_name = review_outline.title_candidates[0] if review_outline.title_candidates else uploaded.name
                except Exception as exc:
                    st.error(f"解析失败：{exc}")
        else:
            pasted = st.text_area("粘贴大纲文本", height=220, placeholder="可粘贴大纲 Markdown / 简介 / 设定摘要，用于本地避撞审查", key="collision_pasted_text")
            if pasted.strip():
                review_outline = pasted.strip()
                outline_name = "粘贴大纲"

        category_filter = st.text_input("分类过滤", value="", placeholder="例如：都市脑洞；留空则按全库", key="collision_category_filter")
        min_score = st.slider("最低风险分", 0, 90, 30, 5, key="collision_min_score")
        top_n = st.slider("最多结果", 5, 100, 30, 5, key="collision_top_n")
        include_all = st.checkbox("全库对比", value=True, key="collision_include_all")
        sample_books = list_books(limit=10_000, category=None if include_all or not category_filter.strip() else category_filter.strip())
        st.caption(f"当前样本：{len(sample_books)} 条")
        if st.button("开始防撞审查", type="primary", width="stretch", disabled=review_outline is None, key="run_collision_review"):
            findings = compare_outline_to_books(review_outline, sample_books, min_score=float(min_score), top_n=int(top_n))
            st.session_state["collision_findings"] = findings
            st.session_state["collision_outline_name"] = outline_name
            st.session_state["collision_sample_size"] = len(sample_books)
            st.success("审查完成" if not findings else f"发现 {len(findings)} 条风险")

        with st.expander("改稿方向", expanded=False):
            st.write("命中风险时优先改职业、能力代价、第一卷目标、反派动机和场景关系。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_report:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("REPORT", "风险报告", "先看风险分布，再处理可执行建议。")
        if findings is None:
            empty_state("还没有审查报告", "在“审查设置”中开始防撞审查后，这里会展示风险列表和 Markdown 报告。")
        else:
            high = sum(1 for f in findings if "高" in str(f.get("risk_level", "")) or float(f.get("score", 0)) >= 70)
            mid = sum(1 for f in findings if ("中" in str(f.get("risk_level", "")) or 45 <= float(f.get("score", 0)) < 70) and not ("高" in str(f.get("risk_level", ""))))
            low = max(len(findings) - high - mid, 0)
            stat_strip([("高风险", str(high), "优先处理"), ("中风险", str(mid), "需要调整"), ("低风险", str(low), "留意变量"), ("总命中", str(len(findings)), "本轮结果")])
            if findings:
                rows = [
                    {
                        "风险": f.get("risk_level"),
                        "分数": f.get("score"),
                        "书名": f.get("title"),
                        "分类": f.get("category"),
                        "重合点": f.get("reason"),
                        "建议": f.get("advice"),
                        "来源": f.get("source_url"),
                    }
                    for f in findings
                ]
                st.dataframe(rows, width="stretch", hide_index=True)
                md = report_to_markdown(st.session_state.get("collision_outline_name", "outline"), findings, st.session_state.get("collision_sample_size", 0))
                tab_action, tab_md = st.tabs(["修改建议", "Markdown"])
                with tab_action:
                    for f in findings[:8]:
                        info_card(
                            f"{f.get('risk_level')} · {f.get('title')}",
                            f"重合点：{f.get('reason') or '未说明'}｜建议：{f.get('advice') or '调整核心变量'}",
                            icon="⚠️",
                        )
                with tab_md:
                    st.markdown(md)
                st.download_button("下载报告", data=md, file_name="collision_review.md", mime="text/markdown", width="stretch")
                if st.button("保存到 outputs/reviews", width="stretch", key="save_collision_report"):
                    path = save_collision_report(st.session_state.get("collision_outline_name", "outline"), findings, st.session_state.get("collision_sample_size", 0))
                    st.success(f"已保存：{path}")
                nav_button("chapter", "下一步：生成正文", "📖", key="nav_collision_to_chapter")
            else:
                st.success("未发现明显撞文风险。")
                nav_button("chapter", "下一步：生成正文", "📖", key="nav_collision_to_chapter")
        st.markdown('</div>', unsafe_allow_html=True)


def render_chapter_page() -> None:
    outline = normalize_outline(st.session_state.get("outline"))
    chapter = normalize_chapter(st.session_state.get("chapter_draft") or st.session_state.get("edit_chapter"))
    page_header(
        "CHAPTER WORKSHOP",
        "📖 章节工坊",
        "按起始章节、章数和目标字数分批生成；生成、编辑、审核和章节库都在 tabs 里完成。",
        "分场景生成",
    )
    stat_strip(
        [
            ("当前大纲", current_outline_title(), "正文依据"),
            ("最近章节", latest_chapter_label(), "会话进度"),
            ("章节版本", str(len(list_chapter_files())), "outputs/chapters"),
            ("正文长度", str(content_length(chapter.content)) if chapter else "未生成", "当前章节"),
        ]
    )

    tab_gen, tab_edit, tab_audit, tab_library = st.tabs(["生成", "编辑", "审核", "章节库"])
    with tab_gen:
        if not outline:
            empty_state("没有可用大纲", "正文生成需要先有当前大纲。请生成或加载大纲后再进入章节工坊。")
            nav_button("outline", "去题材与大纲", "✍️", key="nav_review_to_outline")
        else:
            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("GENERATE", "生成设置", "只生成你选择的章节数，后续可以继续修改和润色。")
            title = outline.title_candidates[0] if outline.title_candidates else "未命名大纲"
            st.caption(f"当前大纲：**{title}**")
            start_chapter = st.number_input("起始章节", 1, 1500, 1, key="chapter_start_no")
            chapter_count = st.number_input("生成章数", 1, 20, 1, key="chapter_count")
            target_words = st.number_input("每章目标字数", 500, 8000, 4500, 500, key="article_target_words")
            generate_mode = st.selectbox("正文模式", ["番茄快节奏", "强冲突爽文", "细腻情绪", "悬疑拉钩子", "自定义"], key="chapter_generate_mode")
            previous_context = st.text_area("前文衔接", height=120, placeholder="粘贴上一章末尾、人物状态、未解决冲突；第一章可留空", key="chapter_previous_context")
            default_req = {
                "番茄快节奏": "开篇三段内进入冲突；多动作和对话；少解释；章末强钩子。",
                "强冲突爽文": "强化压迫、反击、打脸预期；主角赢得合理但不要无脑开挂。",
                "细腻情绪": "强化人物欲望、羞耻感、亲情/友情/爱情张力，但保持网文节奏。",
                "悬疑拉钩子": "用信息差、误导、反转和章末新线索推进，不要故弄玄虚。",
                "自定义": "",
            }[generate_mode]
            requirements = st.text_area("额外写作要求", height=140, value=default_req, placeholder="本轮正文特别要求：冲突强度、对话比例、视角、不能改动的剧情", key=f"chapter_requirements_{generate_mode}")
            with st.expander("本次注入的正文约束", expanded=False):
                st.text(active_skill_constraints("chapter") or "未启用")
            if st.button("生成选定章节并保存", type="primary", width="stretch", key="generate_chapters_button"):
                try:
                    req = inject_skill_text(requirements, "chapter")
                    with st.spinner("正在分场景生成正文，请不要关闭窗口……"):
                        chapters = generate_chapter_series(outline, int(start_chapter), int(chapter_count), int(target_words), previous_context, req)
                    rows = []
                    for new_chapter in chapters:
                        json_path, md_path = save_chapter_files(new_chapter)
                        audit = audit_chapter_against_outline(outline, new_chapter, target_words=int(target_words))
                        audit_json_path, audit_md_path = save_chapter_audit(audit)
                        rows.append(
                            {
                                "章节": new_chapter.chapter_no,
                                "标题": new_chapter.title,
                                "目标": new_chapter.target_words or int(target_words),
                                "实际": new_chapter.actual_length or content_length(new_chapter.content),
                                "审核": f"{audit.verdict} · {audit.score}",
                                "JSON": str(json_path),
                                "Markdown": str(md_path),
                                "审核报告": str(audit_md_path),
                            }
                        )
                        st.session_state["chapter_audit"] = audit.model_dump()
                    st.session_state["generated_chapters"] = chapters
                    if chapters:
                        st.session_state["chapter_draft"] = chapters[-1]
                    st.success(f"已生成 {len(chapters)} 章")
                    st.dataframe(rows, width="stretch", hide_index=True)
                except Exception as exc:
                    st.error(f"正文生成失败：{exc}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("PLAN", "章节计划与成稿", "计划来自当前大纲；成稿保存后会进入章节库。")
            plans = [chapter_plan_from_outline(outline, int(start_chapter) + i) for i in range(int(chapter_count))]
            plan_rows = [
                {"章节": p.get("chapter"), "标题": p.get("title"), "目标": p.get("goal"), "冲突": p.get("conflict"), "钩子": p.get("ending_hook")}
                for p in plans
            ]
            st.dataframe(plan_rows, width="stretch", hide_index=True)
            generated = st.session_state.get("generated_chapters") or []
            if generated:
                labels = [f"第 {c.chapter_no} 章：{c.title}" for c in generated]
                picked = st.selectbox("预览已生成章节", labels, index=len(labels) - 1, key="generated_chapter_preview")
                preview_chapter = generated[labels.index(picked)]
                st.markdown(
                    f"<div class='soft-note'>正文长度约：{content_length(preview_chapter.content)}；目标：{preview_chapter.target_words or target_words}</div>",
                    unsafe_allow_html=True,
                )
                if preview_chapter.generation_notes:
                    with st.expander("生成字数记录", expanded=False):
                        st.write("\n".join(f"- {x}" for x in preview_chapter.generation_notes))
                st.markdown(chapter_to_markdown(preview_chapter))
            else:
                empty_state("还没有本轮生成结果", "点击上方按钮后，成稿会在这里预览。")
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_edit:
        edit_chapter = normalize_chapter(st.session_state.get("edit_chapter") or st.session_state.get("chapter_draft"))
        if st.button("打开章节文件库", width="stretch", key="edit_load_chapter"):
            load_chapter_dialog()
        st.caption(st.session_state.get("edit_chapter_source", "当前会话章节"))
        if not edit_chapter:
            empty_state("请先加载或生成章节", "生成正文后可直接编辑；也可以从章节库加载历史 JSON。")
        else:
            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("POLISH", "AI 润色", "先保存人工修改，再基于当前版本执行 AI 润色并另存。")
            st.markdown(
                f"""
                <div class="soft-note">
                  第 {edit_chapter.chapter_no} 章 · {ui_escape(edit_chapter.title)}｜当前长度：{content_length(edit_chapter.content)} 字｜目标：{edit_chapter.target_words or '未指定'} 字
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not outline:
                st.warning("AI 润色需要当前大纲。")
            else:
                modes = st.multiselect(
                    "润色方向",
                    ["增强冲突", "压缩拖沓", "润色对白", "强化情绪", "降低 AI 味", "强化章末钩子", "保持剧情不变", "扩写细节", "原创避撞"],
                    default=["增强冲突", "润色对白", "降低 AI 味", "强化章末钩子", "保持剧情不变"],
                    key="chapter_polish_modes",
                )
                keep_plot = st.checkbox("保持关键剧情不变", value=True, key="chapter_keep_plot")
                target = st.number_input("润色目标字数（0=不指定）", 0, 10000, 0, 500, key="chapter_polish_target")
                polish_notes = st.text_area("润色意见", value="保留主线事件，增强对白冲突和情绪压迫，去掉模板化表达，让章末钩子更狠。", placeholder="说明要保留什么、删掉什么、增强什么，避免只写“润色一下”", height=150, key="chapter_polish_notes")
                if st.button("AI 润色并另存版本", type="primary", width="stretch", key="polish_chapter_button"):
                    try:
                        review = ChapterReview(
                            reviewer_notes=inject_skill_text(inject_skill_text(polish_notes, "polish", "章节润色约束"), "chapter", "正文约束"),
                            polish_modes=modes,
                            keep_plot_unchanged=keep_plot,
                            target_words=int(target) if int(target) > 0 else None,
                        )
                        polished = polish_chapter(outline, edit_chapter, review)
                        polished.actual_length = content_length(polished.content)
                        json_path, md_path = save_chapter_files(polished)
                        st.session_state["edit_chapter"] = polished
                        st.session_state["chapter_draft"] = polished
                        st.session_state["edit_chapter_version"] = st.session_state.get("edit_chapter_version", 0) + 1
                        st.success(f"已保存：{md_path.name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"润色失败：{exc}")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("EDITOR", "章节编辑器", "修改正文、目标和钩子后保存为新版本。")
            version = st.session_state.get("edit_chapter_version", 0)
            key = f"chapter_edit_{version}"
            with st.form("chapter_edit_form"):
                edited_no = st.number_input("章节序号", 1, 1500, int(edit_chapter.chapter_no), key=f"{key}_no")
                edited_title = st.text_input("章节标题", value=edit_chapter.title, placeholder="例如：第一个代价", key=f"{key}_title")
                edited_pov = st.text_input("叙事视角", value=edit_chapter.pov, placeholder="第三人称有限视角 / 第一人称", key=f"{key}_pov")
                edited_goal = st.text_area("本章目标", value=edit_chapter.chapter_goal, placeholder="本章必须推进到哪里，读者看完应获得什么信息", height=80, key=f"{key}_goal")
                edited_conflict = st.text_area("核心冲突", value=edit_chapter.conflict, placeholder="外部阻力 + 主角选择 + 代价", height=80, key=f"{key}_conflict")
                edited_content = st.text_area("正文内容", value=edit_chapter.content, placeholder="在这里人工改正文，再保存为新版本", height=620, key=f"{key}_content")
                edited_hook = st.text_area("章末钩子", value=edit_chapter.ending_hook, placeholder="最后一段留下的新危机、新秘密或新选择", height=90, key=f"{key}_hook")
                save_manual = st.form_submit_button("保存人工修改版本", type="primary", width="stretch")
            if save_manual:
                updated = ChapterDraft(
                    outline_title=edit_chapter.outline_title,
                    chapter_no=int(edited_no),
                    title=edited_title.strip() or edit_chapter.title,
                    pov=edited_pov.strip() or edit_chapter.pov,
                    chapter_goal=edited_goal.strip(),
                    conflict=edited_conflict.strip(),
                    content=edited_content.strip(),
                    ending_hook=edited_hook.strip(),
                    continuity_notes=edit_chapter.continuity_notes,
                    originality_notes=edit_chapter.originality_notes,
                    next_chapter_seed=edit_chapter.next_chapter_seed,
                    target_words=edit_chapter.target_words,
                    actual_length=content_length(edited_content),
                    generation_notes=edit_chapter.generation_notes + ["人工修改保存。"],
                )
                json_path, md_path = save_chapter_files(updated)
                st.session_state["edit_chapter"] = updated
                st.session_state["chapter_draft"] = updated
                st.session_state["edit_chapter_version"] = st.session_state.get("edit_chapter_version", 0) + 1
                st.success(f"已保存：{md_path.name}")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_audit:
        if not outline:
            empty_state("缺少当前大纲", "章节审核需要用当前大纲作为对照。")
            nav_button("outline", "去加载大纲", "✍️", key="nav_audit_to_outline")
        else:
            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("AUDIT", "章节对照审核", "检查本章是否跑题、是否兑现计划。")
            audit_source = st.segmented_control(
                "审核来源",
                ["当前章节", "本轮生成", "章节文件"],
                default="当前章节",
                key="chapter_audit_source",
            ) or "当前章节"
            audit_chapter = normalize_chapter(st.session_state.get("edit_chapter") or st.session_state.get("chapter_draft"))
            audit_source_path = "当前会话"
            if audit_source == "本轮生成":
                generated = st.session_state.get("generated_chapters") or []
                if generated:
                    labels = [f"第 {c.chapter_no} 章：{c.title}" for c in generated]
                    picked = st.selectbox("选择本轮章节", labels, key="audit_generated_pick")
                    audit_chapter = generated[labels.index(picked)]
                    audit_source_path = "本轮生成"
                else:
                    audit_chapter = None
                    st.info("暂无本轮生成章节。")
            elif audit_source == "章节文件":
                files = list_chapter_files()
                if files:
                    labels = [p.name for p in files]
                    picked = st.selectbox("选择章节文件", labels, key="audit_file_pick")
                    path = files[labels.index(picked)]
                    audit_chapter = load_chapter_from_path(path)
                    audit_source_path = str(path)
                else:
                    audit_chapter = None
                    st.info("暂无章节文件。")

            if audit_chapter:
                plan = chapter_plan_from_outline(outline, int(audit_chapter.chapter_no))
                st.markdown(
                    f"<div class='soft-note'>第 {audit_chapter.chapter_no} 章 · {ui_escape(audit_chapter.title)}｜长度 {content_length(audit_chapter.content)} 字｜来源：{ui_escape(audit_source_path)}</div>",
                    unsafe_allow_html=True,
                )
                with st.expander("对照章节计划", expanded=True):
                    st.json(plan)
            else:
                empty_state("没有可审核章节", "先生成、加载或选择一个章节。")

            if st.button("开始章节审核", type="primary", width="stretch", disabled=audit_chapter is None, key="run_chapter_audit"):
                audit = audit_chapter_against_outline(outline, audit_chapter)  # type: ignore[arg-type]
                json_path, md_path = save_chapter_audit(audit)
                st.session_state["chapter_audit"] = audit.model_dump()
                st.session_state["chapter_audit_paths"] = {"json": str(json_path), "md": str(md_path)}
                st.success(f"审核完成：{audit.verdict} · {audit.score} 分")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("RESULT", "审核结果", "单章报告会保存到 outputs/reviews/chapters。")
            audit_data = st.session_state.get("chapter_audit")
            if not audit_data:
                empty_state("暂无审核结果", "选择章节后开始审核。")
            else:
                audit = audit_data if hasattr(audit_data, "model_dump") else None
                if audit is None:
                    from fanqie_novel_lab.services.chapter_reviewer import ChapterAudit

                    audit = ChapterAudit(**audit_data)
                stat_strip(
                    [
                        ("结论", audit.verdict, "章节质量"),
                        ("分数", str(audit.score), "满分 100"),
                        ("命中", str(len(audit.matched_plan_keywords)), "计划关键词"),
                        ("缺失", str(len(audit.missing_plan_keywords)), "待补关键词"),
                    ]
                )
                st.markdown(f"<div class='soft-note'>{ui_escape(audit.summary)}</div>", unsafe_allow_html=True)
                st.dataframe(audit.checks, width="stretch", hide_index=True)
                audit_tab_advice, audit_tab_missing = st.tabs(["修改建议", "缺失关键词"])
                with audit_tab_advice:
                    if audit.revision_advice:
                        for item in audit.revision_advice:
                            st.markdown(f"- {item}")
                    else:
                        st.caption("暂无明显问题。")
                with audit_tab_missing:
                    st.write("、".join(audit.missing_plan_keywords[:20]) or "无")
                md = audit_to_markdown(audit)
                st.download_button("下载章节审核报告", data=md, file_name=f"chapter_{audit.chapter_no}_audit.md", mime="text/markdown", width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="editor-section">', unsafe_allow_html=True)
            section_intro("HISTORY", "历史审核", "最近的单章审核报告。")
            rows = file_table(list_chapter_audit_files(), 20)
            if rows:
                st.dataframe(rows, width="stretch", hide_index=True)
            else:
                st.caption("暂无历史审核。")
            st.markdown('</div>', unsafe_allow_html=True)

    with tab_library:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("LIBRARY", "章节版本库", "读取 outputs/chapters 下的真实文件。")
        files = list_chapter_files()
        rows = file_table(files, 80)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
            render_history_delete_panel(files, key_prefix="chapter_library", allowed_dir=CHAPTER_DIR, item_label="章节")
        else:
            empty_state("暂无章节文件", "生成或保存章节后会出现在这里。")
        st.markdown('</div>', unsafe_allow_html=True)


def render_publish_page() -> None:
    outline = normalize_outline(st.session_state.get("outline"))
    chapter = normalize_chapter(st.session_state.get("chapter_draft") or st.session_state.get("edit_chapter"))
    works = list_work_profiles()
    packages = list_publish_packages()
    page_header(
        "PUBLISH CENTER",
        "🚀 发布中心",
        "管理作品档案、章节上传包、发布队列和作家后台助手。",
        "发布中心",
    )
    stat_strip(
        [
            ("作品档案", str(len(works)), "本地管理"),
            ("上传包", str(len(packages)), "待上传/已上传"),
            ("当前章节", latest_chapter_label(), "上传来源"),
            ("后台", "番茄作家", "手动确认提交"),
        ]
    )

    tab_work, tab_upload, tab_queue, tab_assist = st.tabs(["作品", "上传包", "队列", "作家助手"])

    with tab_work:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("WORK", "作品档案", "本地管理作品基础信息。")
        labels = ["新建作品"] + [f"{w.title or '未命名'} · {w.id}" for w in works]
        selected_label = st.selectbox("选择档案", labels, key="publish_work_select")
        selected_work = None if selected_label == "新建作品" else works[labels.index(selected_label) - 1]
        seed = work_from_outline(outline) if outline and selected_work is None else None
        base = selected_work or seed or WorkProfile(id="")
        form_key = selected_work.id if selected_work else "new"
        with st.form(f"publish_work_form_{form_key}"):
            title = st.text_input("作品名", value=base.title or current_outline_title(), placeholder="后台作品名，可先用候选书名", key=f"work_title_{form_key}")
            author_pen_name = st.text_input("笔名", value=base.author_pen_name, placeholder="你的平台笔名", key=f"work_author_{form_key}")
            category = st.text_input("分类/频道", value=base.category, placeholder="例如：都市 / 玄幻 / 悬疑", key=f"work_category_{form_key}")
            audience = st.text_input("目标读者", value=base.audience, placeholder="例如：男频爽文读者 / 女频情感读者", key=f"work_audience_{form_key}")
            tags_text = st.text_area("标签（一行一个）", value="\n".join(base.tags), placeholder="一行一个：系统流、重生、悬疑、爽文", height=110, key=f"work_tags_{form_key}")
            intro = st.text_area("作品简介", value=base.intro, placeholder="用于后台简介，可从当前大纲自动带出后再人工修", height=150, key=f"work_intro_{form_key}")
            status = st.selectbox("本地状态", ["本地筹备", "已建作品", "连载中", "暂停", "完结"], index=["本地筹备", "已建作品", "连载中", "暂停", "完结"].index(base.status) if base.status in ["本地筹备", "已建作品", "连载中", "暂停", "完结"] else 0, key=f"work_status_{form_key}")
            fanqie_work_id = st.text_input("平台作品 ID/URL", value=base.fanqie_work_id, placeholder="可填后台作品 URL 或作品 ID", key=f"work_fanqie_id_{form_key}")
            notes = st.text_area("备注", value=base.notes, placeholder="例如：已建作品、待改简介、封面未定", height=90, key=f"work_notes_{form_key}")
            saved = st.form_submit_button("保存作品档案", type="primary", width="stretch")
        if saved:
            work_id = selected_work.id if selected_work else f"work_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            work = WorkProfile(
                id=work_id,
                title=title.strip(),
                author_pen_name=author_pen_name.strip(),
                category=category.strip(),
                audience=audience.strip(),
                tags=[x.strip() for x in tags_text.splitlines() if x.strip()],
                intro=intro.strip(),
                status=status,
                fanqie_work_id=fanqie_work_id.strip(),
                notes=notes.strip(),
                created_at=selected_work.created_at if selected_work else datetime.now().isoformat(timespec="seconds"),
            )
            path = save_work_profile(work)
            st.success(f"已保存作品档案：{path.name}")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("LIBRARY", "作品列表", "本地文件：outputs/publishing/works")
        if works:
            st.dataframe(
                [
                    {
                        "作品": w.title,
                        "笔名": w.author_pen_name,
                        "分类": w.category,
                        "状态": w.status,
                        "标签": "、".join(w.tags[:5]),
                        "平台ID/URL": w.fanqie_work_id,
                        "更新时间": w.updated_at,
                    }
                    for w in works
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            empty_state("暂无作品档案", "可以从当前大纲自动带出作品名、简介、标签，再保存为本地档案。")
        if outline:
            with st.expander("当前大纲可带出的作品信息", expanded=False):
                render_outline_snapshot(outline)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_upload:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("UPLOAD PACK", "一键准备上传包", "生成后台可粘贴的标题、正文、TXT/Markdown/JSON。")
        work_options = ["不绑定作品档案"] + [f"{w.title or '未命名'} · {w.id}" for w in works]
        work_pick = st.selectbox("绑定作品", work_options, key="upload_work_pick")
        picked_work = None if work_pick == "不绑定作品档案" else works[work_options.index(work_pick) - 1]
        source_mode = st.segmented_control("章节来源", ["当前会话章节", "章节文件"], default="当前会话章节", key="upload_source_mode") or "当前会话章节"
        source_chapter = chapter
        source_path = "当前会话"
        if source_mode == "章节文件":
            files = list_chapter_files()
            if files:
                file_labels = [p.name for p in files]
                picked_file = st.selectbox("选择章节 JSON", file_labels, key="upload_chapter_file")
                path = files[file_labels.index(picked_file)]
                source_chapter = load_chapter_from_path(path)
                source_path = str(path)
            else:
                source_chapter = None
                st.warning("暂无章节文件。")
        min_words = st.number_input("最低建议字数", 300, 6000, 1000, 100, key="publish_min_words", help="低于该字数会在上传包检查中标记为风险，不会阻止导出。")
        max_words = st.number_input("最高建议字数", 1000, 15000, 8000, 500, key="publish_max_words", help="高于该字数会提示拆章或删改。")
        if source_chapter:
            info_card(
                f"第 {source_chapter.chapter_no} 章 · {source_chapter.title}",
                f"当前长度：{content_length(source_chapter.content)} 字。",
                icon="📖",
            )
        else:
            empty_state("没有可打包章节", "先在章节工坊生成正文，或从章节文件中选择一个 JSON。")
        if st.button("一键生成上传包", type="primary", width="stretch", disabled=source_chapter is None, key="make_publish_pack"):
            pkg = package_from_chapter(source_chapter, picked_work, source_path)  # type: ignore[arg-type]
            pkg.preflight = validate_publish_package(pkg, min_words=int(min_words), max_words=int(max_words))
            if outline and source_chapter:
                audit = audit_chapter_against_outline(outline, source_chapter)
                audit_json_path, audit_md_path = save_chapter_audit(audit)
                pkg.preflight.append(
                    {
                        "项目": "章节对纲审核",
                        "通过": audit.score >= 68 and audit.verdict != "疑似跑题",
                        "级别": "通过" if audit.score >= 68 and audit.verdict != "疑似跑题" else "error",
                        "说明": f"{audit.verdict} · {audit.score} 分",
                        "建议": "先处理章节审核报告，再上传。" if audit.score < 68 or audit.verdict == "疑似跑题" else "",
                        "报告": str(audit_md_path),
                    }
                )
                st.session_state["chapter_audit"] = audit.model_dump()
            json_path, txt_path, md_path = save_publish_package(pkg)
            st.session_state["publish_current_package"] = pkg.model_dump()
            st.session_state["publish_current_paths"] = {"json": str(json_path), "txt": str(txt_path), "md": str(md_path)}
            st.success(f"上传包已生成：{txt_path.name}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("PREVIEW", "上传内容预览", "这里展示最近生成的上传包，可下载或复制到后台。")
        pkg_data = st.session_state.get("publish_current_package")
        if pkg_data:
            pkg = PublishPackage(**pkg_data)
            failed = [x for x in pkg.preflight if not x.get("通过")]
            st.markdown(
                f"<div class='soft-note'>作品：{ui_escape(pkg.work_title or '未绑定')}｜第 {pkg.chapter_no} 章｜{pkg.length} 字｜检查风险 {len(failed)} 项</div>",
                unsafe_allow_html=True,
            )
            st.download_button("下载后台 TXT", data=package_to_txt(pkg), file_name=f"第{pkg.chapter_no:03d}章_{safe_name(pkg.chapter_title)}.txt", mime="text/plain", width="stretch")
            st.download_button("下载审核 Markdown", data=package_to_markdown(pkg), file_name="publish_package.md", mime="text/markdown", width="stretch")
            st.download_button("下载结构化 JSON", data=json.dumps(pkg.model_dump(), ensure_ascii=False, indent=2), file_name="publish_package.json", mime="application/json", width="stretch")
            st.text_input("后台章节标题", value=pkg.chapter_title, placeholder="复制到作家后台的章节标题", key="publish_preview_title")
            st.text_area("后台正文", value=pkg.content, placeholder="复制到作家后台的正文；最终提交前仍建议人工读一遍", height=430, key="publish_preview_content")
            st.caption("复制标题和正文到番茄作家后台前，请再次确认作品、章节序号和正文内容。")
        else:
            empty_state("还没有上传包", "选择章节后点击“一键生成上传包”。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_queue:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("QUEUE", "发布队列", "本地跟踪待上传、草稿、已发布和需修改状态。")
        packages = list_publish_packages()
        if not packages:
            empty_state("暂无发布队列", "生成上传包后会自动进入队列。")
        else:
            st.dataframe(
                [
                    {
                        "状态": p.upload_status,
                        "作品": p.work_title,
                        "章节": f"第 {p.chapter_no} 章",
                        "标题": p.chapter_title,
                        "字数": p.length,
                        "检查风险": len([x for x in p.preflight if not x.get("通过")]),
                        "更新时间": p.updated_at,
                        "ID": p.id,
                    }
                    for p in packages
                ],
                width="stretch",
                hide_index=True,
            )
            labels = [f"{p.upload_status} · {p.work_title or '未绑定'} · 第{p.chapter_no}章 · {p.chapter_title}" for p in packages]
            picked = st.selectbox("更新队列项", labels, key="queue_package_pick")
            pkg = packages[labels.index(picked)]
            status = st.selectbox("状态", ["待上传", "已上传草稿", "待人工提交", "已发布", "需修改", "暂停"], index=["待上传", "已上传草稿", "待人工提交", "已发布", "需修改", "暂停"].index(pkg.upload_status) if pkg.upload_status in ["待上传", "已上传草稿", "待人工提交", "已发布", "需修改", "暂停"] else 0, key="queue_status")
            notes = st.text_input("备注", value=pkg.operator_notes, placeholder="例如：已复制到后台草稿 / 标题待改 / 章节审核未通过", key="queue_notes")
            if st.button("保存队列状态", type="primary", width="stretch", key="save_queue_status"):
                path = update_package_status(pkg, status, notes)
                st.success(f"状态已更新：{path.name}")
                st.rerun()
            with st.expander("查看提交前检查", expanded=False):
                checks = pkg.preflight or validate_publish_package(pkg)
                st.dataframe(checks, width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_assist:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("FANQIE", "番茄作家助手", "打开后台，配合上传包使用。")
        st.link_button("打开番茄作家后台", FANQIE_WRITER_ZONE_URL, width="stretch")
        st.markdown(
            """
            1. 先在“作品管理”保存作品档案。  
            2. 在“一键上传包”生成章节标题、正文和 TXT。  
            3. 打开番茄作家后台，登录后新建/选择作品。  
            4. 粘贴标题和正文，最终提交前人工确认。
            """
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("AUTOMATION", "自动化清单", "生成给浏览器助手使用的上传清单。")
        st.markdown(
            """
            - ✅ 本地作品管理  
            - ✅ 一键生成上传包  
            - ✅ 提交前字数/格式/AI口吻检查  
            - ✅ 发布队列状态跟踪  
            - ⏸️ 浏览器填表助手：预留入口  
            """
        )
        pkg_data = st.session_state.get("publish_current_package")
        if pkg_data:
            pkg = PublishPackage(**pkg_data)
            automation_manifest = {
                "platform": "番茄小说",
                "writer_zone": FANQIE_WRITER_ZONE_URL,
                "safety_mode": "manual_confirm_before_transmit",
                "work_title": pkg.work_title,
                "chapter_no": pkg.chapter_no,
                "chapter_title": pkg.chapter_title,
                "content_length": pkg.length,
                "next_actions": ["open_writer_zone", "select_work", "paste_title", "paste_content", "stop_before_final_submit"],
            }
            st.download_button(
                "下载自动化清单 JSON",
                data=json.dumps(automation_manifest, ensure_ascii=False, indent=2),
                file_name="fanqie_writer_automation_manifest.json",
                mime="application/json",
                width="stretch",
            )
        else:
            st.caption("生成上传包后，可下载自动化清单。")
        st.markdown('</div>', unsafe_allow_html=True)


def render_export_page() -> None:
    outline = normalize_outline(st.session_state.get("outline"))
    chapter = normalize_chapter(st.session_state.get("chapter_draft") or st.session_state.get("edit_chapter"))
    findings = st.session_state.get("collision_findings")

    page_header(
        "DELIVERY HUB",
        "📦 交付与开源",
        "把作品资产、质量门禁、GitHub 开源检查拆成三个清晰工作区。先看状态，再下载或进入下一步。",
        "真实本地状态",
    )
    stat_strip(
        [
            ("大纲", "可用" if outline else "缺失", "Markdown / JSON"),
            ("章节", "可用" if chapter else "缺失", "Markdown / JSON"),
            ("避撞", "已完成" if findings is not None else "待审查", "报告"),
            ("开源", "检查可用", "GitHub"),
        ]
    )

    tab_assets, tab_gate, tab_github = st.tabs(["资产", "门禁", "开源"])

    with tab_assets:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("STATUS", "交付状态", "只读取当前会话和本地文件。")
        checks = [
            ("大纲已生成", outline is not None),
            ("避撞审查已完成", findings is not None),
            ("章节正文已存在", chapter is not None),
            ("至少一个 Markdown 可导出", outline is not None or chapter is not None),
        ]
        st.markdown(checklist_html(checks), unsafe_allow_html=True)
        if not outline:
            nav_button("outline", "去生成大纲", "✍️", key="nav_export_to_outline")
        elif findings is None:
            nav_button("collision", "去避撞审查", "🛡️", key="nav_export_to_collision")
        elif not chapter:
            nav_button("chapter", "去生成章节", "📖", key="nav_export_to_chapter")
        else:
            nav_button("publish", "去发布中心", "🚀", key="nav_export_to_publish")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("ASSETS", "下载面板", "按资产类型拆分；缺失时只显示下一步，不塞空占位。")
        asset_card("大纲", "完整故事蓝图、卷纲、前十章和风险备注。", outline is not None, "可下载" if outline else "缺失")
        if outline:
            md = outline_to_markdown(outline)
            st.download_button("下载大纲 Markdown", data=md, file_name="outline.md", mime="text/markdown", width="stretch")
            st.download_button("下载大纲 JSON", data=json.dumps(outline.model_dump(), ensure_ascii=False, indent=2), file_name="outline.json", mime="application/json", width="stretch")
            if st.button("另存大纲到 outputs", width="stretch", key="export_save_outline_v2"):
                json_path, md_path, outline_id = save_outline_files(outline, outline.genre_positioning)
                st.success(f"已保存 #{outline_id}: {json_path.name}, {md_path.name}")
        else:
            nav_button("outline", "生成大纲", "✍️", key="nav_asset_outline")

        asset_card("章节", "最近章节正文，支持 Markdown 与结构化 JSON。", chapter is not None, "可下载" if chapter else "缺失")
        if chapter:
            md = chapter_to_markdown(chapter)
            st.download_button("下载章节 Markdown", data=md, file_name=f"chapter_{chapter.chapter_no}.md", mime="text/markdown", width="stretch")
            st.download_button("下载章节 JSON", data=json.dumps(chapter.model_dump(), ensure_ascii=False, indent=2), file_name=f"chapter_{chapter.chapter_no}.json", mime="application/json", width="stretch")
            st.caption(f"第 {chapter.chapter_no} 章 · {chapter.title} · {content_length(chapter.content)} 字")
        else:
            nav_button("chapter", "生成章节", "📖", key="nav_asset_chapter")

        asset_card("避撞报告", "本地公开元数据对比报告。", findings is not None, "可下载" if findings is not None else "未生成")
        if findings is not None:
            md = report_to_markdown(st.session_state.get("collision_outline_name", "outline"), findings, st.session_state.get("collision_sample_size", 0))
            st.download_button("下载避撞报告", data=md, file_name="collision_review.md", mime="text/markdown", width="stretch")
        else:
            nav_button("collision", "生成报告", "🛡️", key="nav_asset_collision")

        asset_card("发布包", "在发布中心生成平台粘贴用 TXT/MD/JSON。", bool(st.session_state.get("publish_current_package")), "已准备" if st.session_state.get("publish_current_package") else "未打包")
        pkg_data = st.session_state.get("publish_current_package")
        if pkg_data:
            pkg = PublishPackage(**pkg_data)
            st.download_button("下载发布 TXT", data=package_to_txt(pkg), file_name=f"chapter_{pkg.chapter_no:03d}.txt", mime="text/plain", width="stretch")
        else:
            nav_button("publish", "制作上传包", "🚀", key="nav_asset_publish")

        with st.expander("快速预览", expanded=False):
            preview_mode = st.segmented_control("预览内容", ["大纲", "章节"], default="大纲", key="export_preview_mode")
            if preview_mode == "大纲" and outline:
                st.markdown(outline_to_markdown(outline))
            elif preview_mode == "章节" and chapter:
                st.markdown(chapter_to_markdown(chapter))
            else:
                st.caption("当前内容缺失，暂无预览。")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("PATH", "输出路径", "生成物默认不提交 Git。")
        for path in ["outputs/outlines", "outputs/chapters", "outputs/reviews", "outputs/publishing"]:
            st.markdown(f"<div class='code-path'>{ui_escape(path)}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_gate:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("GATE", "质量门禁", "导出前最后扫一遍，不自动伪造结论。")
        gate_checks = [
            ("有当前大纲", outline is not None),
            ("有当前章节", chapter is not None),
            ("有避撞审查", findings is not None),
            ("章节可对照大纲审核", outline is not None and chapter is not None),
        ]
        st.markdown(checklist_html(gate_checks), unsafe_allow_html=True)
        if outline and chapter and st.button("立即做章节对纲审核", type="primary", width="stretch", key="export_run_audit"):
            audit = audit_chapter_against_outline(outline, chapter)
            json_path, md_path = save_chapter_audit(audit)
            st.session_state["chapter_audit"] = audit.model_dump()
            st.session_state["chapter_audit_paths"] = {"json": str(json_path), "md": str(md_path)}
            st.success(f"审核完成：{audit.verdict} · {audit.score} 分")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("RESULT", "检查结果", "显示最近一次避撞和章节审核。")
        if outline:
            findings_final = check_outline_similarity(outline, list_books(limit=200))
            if findings_final:
                st.warning("发现相似度风险，请先调整核心设定。")
                st.dataframe(findings_final, width="stretch", hide_index=True)
            else:
                st.success("大纲快速相似度检查通过。")
        else:
            empty_state("缺少大纲", "无法执行相似度检查。")

        audit_data = st.session_state.get("chapter_audit")
        if audit_data:
            from fanqie_novel_lab.services.chapter_reviewer import ChapterAudit

            audit = audit_data if hasattr(audit_data, "model_dump") else ChapterAudit(**audit_data)
            st.markdown(f"<div class='soft-note'>章节审核：{ui_escape(audit.verdict)} · {audit.score}/100</div>", unsafe_allow_html=True)
            st.dataframe(audit.checks, width="stretch", hide_index=True)
            md = audit_to_markdown(audit)
            st.download_button("下载章节审核报告", data=md, file_name=f"chapter_{audit.chapter_no}_audit.md", mime="text/markdown", width="stretch")
        else:
            st.caption("暂无章节审核结果。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_github:
        items = scan_open_source_readiness()
        summary = readiness_summary(items)
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("OPEN SOURCE", "GitHub 发布状态", "README、License、CI、模板和忽略规则。")
        stat_strip(
            [
                ("分数", f"{summary['score']}/100", str(summary["verdict"])),
                ("通过", str(summary["pass"]), "检查项"),
                ("待处理", str(summary["fail"]), "必须清零"),
                ("命令", "check", "CLI"),
            ]
        )
        if summary["fail"]:
            st.error("还有待处理项，先不要 push 到 GitHub。")
        else:
            st.success("开源体检通过。push 前仍需人工看 git status。")
        report_md = readiness_markdown(items)
        st.download_button("下载体检报告", data=report_md, file_name="open_source_readiness.md", mime="text/markdown", width="stretch")
        with st.popover("首次上传命令", width="stretch"):
            st.code(
                """python -m py_compile $(find src -name '*.py')
python -m unittest discover -s tests
fanqie-lab open-source-check
git add -n .
git add .
git status
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/<your-name>/fanqie-novel-lab.git
git push -u origin main""",
                language="bash",
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("CHECKLIST", "开源体检明细", "红项出现前不建议提交。")
        st.dataframe(readiness_rows(items), width="stretch", hide_index=True, height=520)
        st.markdown('</div>', unsafe_allow_html=True)


def render_settings_page() -> None:
    active = get_active_profile()
    page_header(
        "PROJECT SETTINGS",
        "项目设置",
        "模型、约束、历史加载集中到这里；不再放弹窗入口到导航栏里。",
        "本地配置",
    )
    tab_model, tab_rules, tab_history = st.tabs(["模型", "创作约束", "历史"])
    with tab_model:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("MODEL", "模型与中转", "选择已保存 profile，或新增任意 OpenAI-compatible 中转站、本地网关、Claude CLI。")
        profiles = list_profiles()
        if profiles:
            labels = [f"{p.name} · {p.model}" for p in profiles]
            active_index = next((i for i, p in enumerate(profiles) if p.name == active.name), 0)
            picked = st.selectbox("当前模型 profile", labels, index=active_index, key="settings_profile_switch", help="切换后会立即用于大纲、润色、章节生成。")
            picked_profile = profiles[labels.index(picked)]
            if picked_profile.name != active.name:
                set_active_profile(picked_profile.name)
                st.toast(f"已切换模型：{picked_profile.model}")
                st.rerun()
            st.dataframe(model_profile_rows(profiles), width="stretch", hide_index=True)
        st.markdown(
            f"<div class='soft-note'>当前模型：{ui_escape(active.name)} · {ui_escape(active.model)}｜{ui_escape(active.base_url)}<br>配置文件：{ui_escape(PROFILES_PATH)}</div>",
            unsafe_allow_html=True,
        )
        if st.button("新增或编辑模型配置", type="primary", width="stretch", key="settings_model_dialog"):
            model_settings_dialog()
        with st.expander("删除模型配置", expanded=False):
            if len(profiles) <= 1:
                st.caption("至少保留一个模型配置。")
            else:
                deletable = [p.name for p in profiles]
                delete_name = st.selectbox("选择要删除的配置", deletable, key="settings_delete_profile_select")
                confirm_delete_profile = st.checkbox(f"确认删除模型配置：{delete_name}", key="settings_delete_profile_confirm")
                if st.button("删除选中的模型配置", width="stretch", disabled=not confirm_delete_profile, key="settings_delete_profile_button"):
                    try:
                        delete_profile(delete_name)
                        st.warning(f"已删除模型配置：{delete_name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"删除失败：{exc}")
        st.caption("模型列表读取失败时，直接手动填写模型 ID；Base URL 也不会被供应商预设限制。")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab_rules:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("RULES", "创作约束", "约束会注入大纲、正文、润色和避撞提示。")
        skills = selected_skill_names(active_skill_ids())
        st.markdown(chips_html(skills, 12) if skills else "未启用", unsafe_allow_html=True)
        if st.button("编辑创作约束", width="stretch", key="settings_skills_dialog"):
            skills_dialog()
        with st.expander("当前约束全文", expanded=False):
            st.text(active_skill_constraints("outline") or "未启用大纲约束")
            st.text(active_skill_constraints("chapter") or "未启用正文约束")
            st.text(active_skill_constraints("avoid") or "未启用避撞约束")
        st.markdown('</div>', unsafe_allow_html=True)
    with tab_history:
        st.markdown('<div class="editor-section">', unsafe_allow_html=True)
        section_intro("HISTORY", "加载历史", "从本地 outputs 加载已有大纲。")
        if st.button("打开历史大纲库", width="stretch", key="settings_load_outline"):
            load_outline_dialog()
        rows = file_table(saved_outline_files(), 20)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
            render_history_delete_panel(saved_outline_files(), key_prefix="settings_outline", allowed_dir=OUTLINE_DIR, item_label="大纲")
        else:
            st.caption("暂无历史大纲。")
        st.markdown('</div>', unsafe_allow_html=True)


def render_current_app_tab() -> None:
    tab_key = st.session_state.get("app_tab", "outline")
    renderers = {
        "home": render_home,
        "data": render_data_page,
        "outline": render_outline_page,
        "review": render_review_page,
        "collision": render_collision_page,
        "chapter": render_chapter_page,
        "publish": render_publish_page,
        "export": render_export_page,
        "settings": render_settings_page,
    }
    renderers.get(tab_key, render_outline_page)()


inject_theme()
render_sidebar_tools()
render_current_app_tab()
