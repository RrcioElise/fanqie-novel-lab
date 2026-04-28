from __future__ import annotations

import unittest

from fanqie_novel_lab.schemas import ChapterDraft, NovelOutline
from fanqie_novel_lab.services.chapter_generator import content_length
from fanqie_novel_lab.services.chapter_reviewer import audit_chapter_against_outline
from fanqie_novel_lab.services.open_source_readiness import readiness_summary, scan_open_source_readiness
from fanqie_novel_lab.services.publisher import package_from_chapter, validate_publish_package


def sample_outline() -> NovelOutline:
    return NovelOutline(
        title_candidates=["记忆当铺"],
        one_line_pitch="主角用记忆交换线索，查清城市里的异常交易。",
        selling_points=["记忆代价", "都市悬疑", "强钩子"],
        target_reader="男频都市读者",
        genre_positioning="都市脑洞",
        world_setting="现代都市中存在隐藏交易系统。",
        protagonist={"name": "林川", "goal": "找回妹妹失踪真相", "pressure": "债务和记忆流失"},
        key_characters=[{"name": "许青", "role": "线人"}],
        antagonist_design=[{"name": "当铺老板", "motive": "收割记忆"}],
        power_system_or_hook_rules=["每次交易都会失去一段重要记忆", "线索越珍贵，代价越大"],
        volume_plan=[{"chapters": "1-30", "goal": "查清第一家当铺", "main_conflict": "记忆代价不断扩大", "ending_hook": "发现妹妹也交易过记忆"}],
        first_10_chapters=[
            {
                "chapter": 1,
                "title": "三天",
                "goal": "林川发现记忆当铺并得到妹妹线索",
                "conflict": "他必须用最重要的记忆交换线索",
                "twist": "线索指向身边熟人",
                "ending_hook": "妹妹的交易记录出现了他的名字",
            }
        ],
        long_arc=["找回妹妹", "查清当铺来源"],
        recurring_hooks=["记忆缺口", "交易代价"],
        risk_notes=["避免万能金手指"],
    )


class SmokeTests(unittest.TestCase):
    def test_content_length(self) -> None:
        self.assertEqual(content_length("你 好\n世界"), 4)

    def test_chapter_audit_and_publish_package(self) -> None:
        outline = sample_outline()
        chapter = ChapterDraft(
            outline_title="记忆当铺",
            chapter_no=1,
            title="三天",
            chapter_goal="林川发现记忆当铺并得到妹妹线索",
            conflict="他必须用最重要的记忆交换线索",
            content=(
                "林川推开记忆当铺的门，柜台后的老板抬头说：\n"
                "“妹妹的线索，需要用你最重要的记忆交换。”\n"
                "债务催收的短信还在震动，妹妹已经失踪三天，他没有退路。\n"
                "“换。”林川咬牙。\n"
                "交易完成后，他忘掉了母亲的声音，却拿到一张旧车票。\n"
                "许青认出车票，脸色骤变：“这是你身边熟人的车。”\n"
                "林川追问线索，许青却拦住他：“别查，当铺会继续收走你的记忆。”\n"
                "他低头看向交易记录，最后一栏赫然写着林川的名字。\n"
                "妹妹的交易记录，为什么会出现他的名字？"
            ),
            ending_hook="妹妹的交易记录出现了他的名字",
            target_words=120,
        )
        audit = audit_chapter_against_outline(outline, chapter)
        self.assertGreaterEqual(audit.score, 50)
        package = package_from_chapter(chapter)
        checks = validate_publish_package(package, min_words=50, max_words=2000)
        self.assertTrue(any(item["项目"] == "正文内容" for item in checks))

    def test_open_source_readiness_scan(self) -> None:
        items = scan_open_source_readiness()
        summary = readiness_summary(items)
        self.assertGreaterEqual(summary["score"], 80)
        self.assertTrue(any(item.item == "README.md" and item.status == "pass" for item in items))
        self.assertTrue(any(item.item == ".env" and item.status == "pass" for item in items))


if __name__ == "__main__":
    unittest.main()
