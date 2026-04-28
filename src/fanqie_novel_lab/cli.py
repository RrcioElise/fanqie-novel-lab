from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .crawler.fanqie_public import crawl_public_metadata, crawl_rank_api, fetch_rank_categories
from .db import clear_books, init_db, list_books, upsert_books
from .io_utils import books_from_csv
from .schemas import ChapterReview, OutlineReview, TopicBrief
from .services.outline_generator import generate_outline, polish_outline, save_outline_files
from .services.similarity_guard import check_outline_similarity
from .services.trend_analyzer import analyze_trends
from .services.collision_reviewer import compare_outline_to_books, report_to_markdown, save_collision_report
from .services.chapter_generator import generate_chapter_series, load_chapter_from_path, polish_chapter, save_chapter_files
from .services.chapter_reviewer import audit_chapter_against_outline, audit_to_markdown, save_chapter_audit
from .services.open_source_readiness import (
    readiness_json,
    readiness_markdown,
    readiness_rows,
    readiness_summary,
    scan_open_source_readiness,
)

app = typer.Typer(help="番茄小说公开元数据分析 + 原创大纲生成人审流")
console = Console()




@app.command("rank-categories")
def rank_categories_cmd() -> None:
    rows = fetch_rank_categories()
    table = Table(title="番茄公开榜单分类")
    for col in ["gender", "id", "name"]:
        table.add_column(col)
    for row in rows:
        table.add_row(str(row["gender_name"]), str(row["id"]), str(row["name"]))
    console.print(table)


@app.command("crawl-rank")
def crawl_rank_cmd(
    category_id: Annotated[str, typer.Option(help="分类 ID，例如 都市脑洞=262")],
    gender: Annotated[int, typer.Option(help="1=男频，0=女频")] = 1,
    rank_mold: Annotated[int, typer.Option(help="1=阅读榜，2=新书榜")] = 1,
    limit: Annotated[int, typer.Option(help="最大采集条数")] = 50,
) -> None:
    books = crawl_rank_api(category_id=category_id, gender=gender, rank_mold=rank_mold, limit=limit)
    count = upsert_books(books)
    console.print(f"[green]采集并保存 {count} 条公开榜单元数据[/green]")
    if any("字体加密待人工校对" in b.tags for b in books):
        console.print("[yellow]提示：番茄网页部分文本使用字体加密，已标记“字体加密待人工校对”。[/yellow]")


@app.command("clear-books")
def clear_books_cmd(sample_only: Annotated[bool, typer.Option(help="只清理示例数据")] = False) -> None:
    count = clear_books(only_sample=sample_only)
    console.print(f"[green]已删除 {count} 条元数据[/green]")


@app.command("init-db")
def init_db_cmd() -> None:
    init_db()
    console.print("[green]数据库已初始化[/green]")


@app.command("import-csv")
def import_csv(path: Annotated[Path, typer.Argument(help="CSV 文件路径")]) -> None:
    books = books_from_csv(str(path))
    count = upsert_books(books)
    console.print(f"[green]已导入/更新 {count} 条元数据[/green]")


@app.command("crawl-url")
def crawl_url(
    url: Annotated[str, typer.Argument(help="公开榜单/分类页 URL")],
    limit: Annotated[int, typer.Option(help="最大采集条数")] = 50,
) -> None:
    books = crawl_public_metadata(url, limit=limit)
    count = upsert_books(books)
    console.print(f"[green]采集并保存 {count} 条公开元数据[/green]")
    if count == 0:
        console.print("[yellow]未解析到数据。页面可能为动态渲染，可改用 CSV 导入。[/yellow]")


@app.command("list-books")
def list_books_cmd(limit: int = 20, category: str | None = None) -> None:
    books = list_books(limit=limit, category=category)
    table = Table(title="元数据样本")
    for col in ["rank", "category", "title", "author", "heat", "score"]:
        table.add_column(col)
    for b in books:
        table.add_row(str(b.rank_no or ""), b.category, b.title, b.author, str(b.heat or ""), str(b.score or ""))
    console.print(table)


@app.command("review-outline")
def review_outline_cmd(
    outline_path: Annotated[Path, typer.Argument(help="大纲 JSON/Markdown/TXT 文件路径")],
    category: Annotated[str | None, typer.Option(help="只对比指定分类，例如 都市脑洞")] = None,
    min_score: Annotated[float, typer.Option(help="最低风险分数")] = 30,
    top_n: Annotated[int, typer.Option(help="最多显示/保存多少条风险")] = 30,
    save: Annotated[bool, typer.Option(help="保存 Markdown 报告")] = True,
) -> None:
    from .schemas import NovelOutline

    raw = outline_path.read_text(encoding="utf-8")
    outline: NovelOutline | str
    if outline_path.suffix.lower() == ".json":
        outline = NovelOutline(**json.loads(raw))
        outline_name = outline.title_candidates[0] if outline.title_candidates else outline_path.stem
    else:
        outline = raw
        outline_name = outline_path.stem
    books = list_books(limit=10_000, category=category)
    findings = compare_outline_to_books(outline, books, min_score=min_score, top_n=top_n)

    table = Table(title=f"大纲防撞审查：{outline_name}")
    for col in ["risk", "score", "title", "category", "reason", "advice"]:
        table.add_column(col)
    for f in findings[:top_n]:
        table.add_row(
            f["risk_level"],
            str(f["score"]),
            f["title"][:30],
            f.get("category") or "",
            (f.get("reason") or "")[:40],
            (f.get("advice") or "")[:45],
        )
    console.print(table)
    if not findings:
        console.print("[green]未发现明显撞文风险。[/green]")
    if save:
        path = save_collision_report(outline_name, findings, len(books))
        console.print(f"[green]报告已保存：{path}[/green]")


@app.command("generate-outline")
def generate_outline_cmd(
    genre: Annotated[str, typer.Option(help="题材，例如 都市脑洞")],
    core_hook: Annotated[str, typer.Option(help="核心钩子/金手指")],
    audience: Annotated[str, typer.Option(help="目标读者")] = "男频",
    style: Annotated[str, typer.Option(help="风格")]= "爽文、节奏快、三章内出爆点",
    avoid: Annotated[str, typer.Option(help="禁忌，用分号分隔")] = "不要仿写具体作品;不要洗稿;不要无脑开挂",
    must_have: Annotated[str, typer.Option(help="必须有，用分号分隔")] = "强开局;持续升级;章节钩子",
    target_words: int = 1_000_000,
    target_chapters: int = 300,
) -> None:
    books = list_books(limit=80, category=genre)
    trend = analyze_trends(genre, books)
    topic = TopicBrief(
        genre=genre,
        audience=audience,
        core_hook=core_hook,
        style=style,
        avoid=[x.strip() for x in avoid.split(";") if x.strip()],
        must_have=[x.strip() for x in must_have.split(";") if x.strip()],
        target_words=target_words,
        target_chapters=target_chapters,
    )
    try:
        outline = generate_outline(topic, trend)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    findings = check_outline_similarity(outline, books)
    json_path, md_path, outline_id = save_outline_files(outline, genre)
    console.print(f"[green]已生成大纲 #{outline_id}[/green]")
    console.print(f"JSON: {json_path}")
    console.print(f"MD:   {md_path}")
    if findings:
        console.print("[yellow]相似度风险提示：[/yellow]")
        console.print(json.dumps(findings[:5], ensure_ascii=False, indent=2))


@app.command("polish-outline")
def polish_outline_cmd(
    outline_json: Annotated[Path, typer.Argument(help="已生成的大纲 JSON")],
    notes: Annotated[str, typer.Option(help="你的审核意见")],
    modes: Annotated[str, typer.Option(help="润色方向，用分号分隔")] = "加强前三章爆点;强化主角动机;金手指规则与代价;降低 AI 味",
    originality_score: int = 7,
    hook_score: int = 7,
    pacing_score: int = 7,
    platform_fit_score: int = 7,
    character_score: int = 7,
) -> None:
    from .schemas import NovelOutline

    outline = NovelOutline(**json.loads(outline_json.read_text(encoding="utf-8")))
    review = OutlineReview(
        originality_score=originality_score,
        hook_score=hook_score,
        pacing_score=pacing_score,
        platform_fit_score=platform_fit_score,
        character_score=character_score,
        reviewer_notes=notes,
        polish_modes=[x.strip() for x in modes.split(";") if x.strip()],
    )
    try:
        polished = polish_outline(outline, review)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    json_path, md_path, outline_id = save_outline_files(polished, genre="polished")
    console.print(f"[green]已润色大纲 #{outline_id}[/green]")
    console.print(f"JSON: {json_path}")
    console.print(f"MD:   {md_path}")


@app.command("generate-chapter")
def generate_chapter_cmd(
    outline_json: Annotated[Path, typer.Argument(help="已生成/润色的大纲 JSON")],
    chapter_no: Annotated[int, typer.Option(help="起始章节序号")] = 1,
    count: Annotated[int, typer.Option(help="本次生成章数，不会默认生成全书")] = 1,
    target_words: Annotated[int, typer.Option(help="每章目标字数")] = 2500,
    previous_context: Annotated[str, typer.Option(help="前文衔接/已发生剧情")] = "",
    requirements: Annotated[str, typer.Option(help="额外写作要求")] = "番茄小说节奏，强冲突，少解释，多动作和对话，章末留钩子。",
) -> None:
    from .schemas import NovelOutline

    outline = NovelOutline(**json.loads(outline_json.read_text(encoding="utf-8")))
    try:
        chapters = generate_chapter_series(
            outline=outline,
            start_chapter=chapter_no,
            chapter_count=count,
            target_words=target_words,
            previous_context=previous_context,
            requirements=requirements,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    table = Table(title=f"已生成并保存 {len(chapters)} 章")
    for col in ["chapter", "title", "json", "markdown"]:
        table.add_column(col)
    for chapter in chapters:
        json_path, md_path = save_chapter_files(chapter)
        table.add_row(str(chapter.chapter_no), chapter.title, str(json_path), str(md_path))
    console.print(table)


@app.command("polish-chapter")
def polish_chapter_cmd(
    outline_json: Annotated[Path, typer.Argument(help="对应的大纲 JSON")],
    chapter_json: Annotated[Path, typer.Argument(help="已生成/人工修改的章节 JSON")],
    notes: Annotated[str, typer.Option(help="你的润色意见")],
    modes: Annotated[str, typer.Option(help="润色方向，用分号分隔")] = "增强冲突;润色对白;降低 AI 味;强化章末钩子;保持剧情不变",
    keep_plot: Annotated[bool, typer.Option(help="保持关键剧情不变")] = True,
    target_words: Annotated[int, typer.Option(help="润色目标字数，0=不指定")] = 0,
) -> None:
    from .schemas import NovelOutline

    outline = NovelOutline(**json.loads(outline_json.read_text(encoding="utf-8")))
    chapter = load_chapter_from_path(chapter_json)
    review = ChapterReview(
        reviewer_notes=notes,
        polish_modes=[x.strip() for x in modes.split(";") if x.strip()],
        keep_plot_unchanged=keep_plot,
        target_words=target_words if target_words > 0 else None,
    )
    try:
        polished = polish_chapter(outline, chapter, review)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    json_path, md_path = save_chapter_files(polished)
    console.print(f"[green]已润色并保存第 {polished.chapter_no} 章：{polished.title}[/green]")
    console.print(f"JSON: {json_path}")
    console.print(f"MD:   {md_path}")


@app.command("audit-chapter")
def audit_chapter_cmd(
    outline_json: Annotated[Path, typer.Argument(help="对应的大纲 JSON")],
    chapter_json: Annotated[Path, typer.Argument(help="章节 JSON")],
    save: Annotated[bool, typer.Option(help="保存 Markdown/JSON 审核报告")] = True,
) -> None:
    """对照大纲审核单章是否跑题、是否兑现计划。"""
    from .schemas import NovelOutline

    outline = NovelOutline(**json.loads(outline_json.read_text(encoding="utf-8")))
    chapter = load_chapter_from_path(chapter_json)
    audit = audit_chapter_against_outline(outline, chapter)

    table = Table(title=f"章节审核：第 {audit.chapter_no} 章《{audit.chapter_title}》")
    for col in ["item", "ok", "level", "deduct", "message"]:
        table.add_column(col)
    for item in audit.checks:
        table.add_row(
            str(item.get("项目", "")),
            "yes" if item.get("通过") else "no",
            str(item.get("级别", "")),
            str(item.get("扣分", 0)),
            str(item.get("说明", ""))[:55],
        )
    console.print(table)
    console.print(f"[bold]{audit.verdict}[/bold] · {audit.score}/100")
    if audit.revision_advice:
        console.print("[yellow]修改建议：[/yellow]")
        for advice in audit.revision_advice:
            console.print(f"- {advice}")
    if save:
        json_path, md_path = save_chapter_audit(audit)
        console.print(f"[green]报告已保存：{json_path}[/green]")
        console.print(f"[green]Markdown：{md_path}[/green]")
    else:
        console.print(audit_to_markdown(audit))


@app.command("open-source-check")
def open_source_check_cmd(
    json_output: Annotated[bool, typer.Option("--json", help="输出 JSON，便于 CI 或脚本读取")] = False,
    markdown_output: Annotated[bool, typer.Option("--markdown", help="输出 Markdown 报告")] = False,
) -> None:
    """检查上传 GitHub 前的开源材料和本地敏感文件忽略状态。"""

    items = scan_open_source_readiness()
    summary = readiness_summary(items)
    if json_output:
        console.print(json.dumps(readiness_json(items), ensure_ascii=False, indent=2))
    elif markdown_output:
        console.print(readiness_markdown(items))
    else:
        table = Table(title=f"Open Source Readiness · {summary['score']}/100 · {summary['verdict']}")
        for col in ["类别", "项目", "状态", "说明"]:
            table.add_column(col)
        for row in readiness_rows(items):
            table.add_row(row["类别"], row["项目"], row["状态"], row["说明"][:80])
        console.print(table)
    if summary["fail"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
