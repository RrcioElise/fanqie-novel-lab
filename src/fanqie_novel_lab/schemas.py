from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BookMeta(BaseModel):
    source_url: str = ""
    rank_name: str = ""
    rank_no: int | None = None
    category: str = ""
    title: str
    author: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    word_count: int | None = None
    heat: float | None = None
    score: float | None = None
    status: str = ""
    updated_at: str = ""
    collected_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class TopicBrief(BaseModel):
    genre: str
    audience: str = ""
    core_hook: str
    style: str = ""
    target_words: int = 1_000_000
    target_chapters: int = 300
    must_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    platform: str = "番茄小说"


class OutlineReview(BaseModel):
    originality_score: int = Field(ge=1, le=10, default=7)
    hook_score: int = Field(ge=1, le=10, default=7)
    pacing_score: int = Field(ge=1, le=10, default=7)
    platform_fit_score: int = Field(ge=1, le=10, default=7)
    character_score: int = Field(ge=1, le=10, default=7)
    reviewer_notes: str = ""
    polish_modes: list[str] = Field(default_factory=list)


class NovelOutline(BaseModel):
    title_candidates: list[str]
    one_line_pitch: str
    selling_points: list[str]
    target_reader: str
    genre_positioning: str
    world_setting: str
    protagonist: dict[str, Any]
    key_characters: list[dict[str, Any]]
    antagonist_design: list[dict[str, Any]]
    power_system_or_hook_rules: list[str]
    volume_plan: list[dict[str, Any]]
    first_10_chapters: list[dict[str, Any]]
    long_arc: list[str]
    recurring_hooks: list[str]
    risk_notes: list[str]
    revision_notes: list[str] = Field(default_factory=list)


class ChapterDraft(BaseModel):
    outline_title: str = ""
    chapter_no: int = 1
    title: str
    pov: str = "第三人称"
    chapter_goal: str = ""
    conflict: str = ""
    content: str
    ending_hook: str = ""
    continuity_notes: list[str] = Field(default_factory=list)
    originality_notes: list[str] = Field(default_factory=list)
    next_chapter_seed: str = ""
    target_words: int | None = None
    actual_length: int | None = None
    generation_notes: list[str] = Field(default_factory=list)


class ChapterReview(BaseModel):
    reviewer_notes: str = ""
    polish_modes: list[str] = Field(default_factory=list)
    keep_plot_unchanged: bool = True
    target_words: int | None = None


class TrendReport(BaseModel):
    genre: str
    sample_size: int
    hot_patterns: list[str]
    common_hooks: list[str]
    reader_expectations: list[str]
    avoid_cliches: list[str]
    originality_opportunities: list[str]
    recommended_outline_rules: list[str]
