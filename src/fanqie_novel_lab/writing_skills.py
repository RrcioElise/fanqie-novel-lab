from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WritingSkill:
    id: str
    icon: str
    name: str
    category: str
    description: str
    outline_constraints: tuple[str, ...]
    chapter_constraints: tuple[str, ...]
    polish_constraints: tuple[str, ...]
    avoid_constraints: tuple[str, ...]
    source_refs: tuple[str, ...] = ()


ALL_WRITING_SKILLS: list[WritingSkill] = [
    WritingSkill(
        id="golden_three_chapters",
        icon="⚡",
        name="黄金三章强钩子",
        category="开篇留存",
        description="前三章快速交代主角压力、核心能力、第一轮冲突和明确期待。",
        outline_constraints=(
            "前三章必须分别承担：建立困境与代入、触发核心钩子、完成第一次可见爽点/反转。",
            "第一章开篇三段内进入具体冲突，不用长背景介绍开局。",
            "前三章结尾都要留下下一章必须点开的悬念。",
        ),
        chapter_constraints=(
            "开篇 300 字内给出具体冲突、异常信息或人物压力，不从天气/世界观长解释开始。",
            "每章至少有一次可见转折：信息差揭露、关系反转、危机升级或爽点兑现。",
            "章末钩子必须指向下一章的具体问题，而不是空泛悬念。",
        ),
        polish_constraints=(
            "检查前三章是否太慢；删除不影响冲突的背景说明。",
            "强化章末钩子，让读者知道下一章会解决/升级什么问题。",
        ),
        avoid_constraints=(
            "避免第一章只有设定介绍、梦境、独白或无冲突日常。",
            "避免前三章没有核心金手指或主线承诺。",
        ),
        source_refs=("GoodNovel Academy", "PHP中文网黄金三章整理"),
    ),
    WritingSkill(
        id="micro_conflict_loop",
        icon="🔁",
        name="单章微冲突循环",
        category="章节节奏",
        description="每章按目标—阻力—升级—转折—钩子推进，避免流水账。",
        outline_constraints=(
            "前 10 章每章都要写清：本章目标、阻力、升级、反转、章末钩子。",
            "卷纲里每 3-5 章安排一次阶段性兑现，不能只铺垫不回报。",
        ),
        chapter_constraints=(
            "每章至少包含一个明确目标、一个外部阻力、一次升级、一次转折和一个章末钩子。",
            "场景之间必须有因果推进，不能只是并列事件堆叠。",
        ),
        polish_constraints=(
            "检查每章是否有目标和阻力；没有冲突的段落应删减或改成冲突场景。",
            "把解释性段落改成行动、对白或选择。",
        ),
        avoid_constraints=(
            "避免连续两章只解释设定或只做日常过渡。",
            "避免章末用‘他不知道的是’这类空泛模板收尾。",
        ),
        source_refs=("Laterpress serial fiction guide", "WritingHub/serial hook discussions"),
    ),
    WritingSkill(
        id="story_bible_continuity",
        icon="📚",
        name="故事圣经连续性",
        category="长篇稳定",
        description="保持人物、设定、能力代价、伏笔和时间线一致。",
        outline_constraints=(
            "大纲必须记录核心设定、能力规则、代价、关键人物关系和长期伏笔。",
            "金手指每次使用要有边界、成本或后果，避免后期崩盘。",
        ),
        chapter_constraints=(
            "生成正文时必须遵守已有能力规则、人物关系和前文状态。",
            "新信息出现时要标记为后续可回收伏笔，不随意新增无用设定。",
        ),
        polish_constraints=(
            "检查人物称呼、能力限制、时间线、伤病/负债/关系状态是否前后一致。",
            "删掉与主线无关且后续不回收的新设定。",
        ),
        avoid_constraints=(
            "避免主角能力突然无代价升级。",
            "避免关键人物动机前后矛盾。",
        ),
        source_refs=("Laterpress Story Tools / story bible", "Story Empire story bible"),
    ),
    WritingSkill(
        id="character_desire_pressure",
        icon="🎭",
        name="人物欲望与压力源",
        category="人物代入",
        description="让主角的欲望、羞耻、债务、亲情或职业压力推动剧情。",
        outline_constraints=(
            "主角必须有具体、可量化、能立刻压迫他的现实压力。",
            "反派/阻力要围绕主角欲望和缺陷施压，而非单纯脸谱化作恶。",
        ),
        chapter_constraints=(
            "每章至少让主角做一次选择：保住尊严、救人、赚钱、守秘密或付出代价。",
            "用对白和动作展示人物欲望，不只用旁白解释。",
        ),
        polish_constraints=(
            "强化主角此刻最怕失去什么、最想得到什么。",
            "让配角的立场与主角目标产生摩擦。",
        ),
        avoid_constraints=(
            "避免主角无欲无求、只被剧情推着走。",
            "避免反派只会嘲讽，不制造实际后果。",
        ),
        source_refs=("GoodNovel Academy curiosity/reader threshold", "PICS controllable story generation"),
    ),
    WritingSkill(
        id="爽点兑现与代价",
        icon="💥",
        name="爽点兑现与代价",
        category="平台适配",
        description="爽点要具体兑现，但不能无脑开挂，必须有成本和后患。",
        outline_constraints=(
            "每个核心爽点都要设计：触发条件、即时收益、隐藏代价、后续反噬。",
            "每卷至少安排 2-3 次阶段性爽点兑现，同时埋下更大危机。",
        ),
        chapter_constraints=(
            "爽点兑现必须可见：赢了什么、打破什么压迫、让谁态度变化。",
            "主角获利后必须留下新问题或代价，形成连载动力。",
        ),
        polish_constraints=(
            "检查爽点是否只是口头爽；补足旁人反应、利益变化和下一轮压力。",
            "给金手指使用增加限制，避免万能解决。",
        ),
        avoid_constraints=(
            "避免主角没有代价地碾压所有人。",
            "避免爽点只靠旁白宣布，没有具体场景。",
        ),
        source_refs=("网文爽点/钩子公开写作资料",),
    ),
    WritingSkill(
        id="anti_collision_originality",
        icon="🛡️",
        name="原创防撞变量",
        category="原创避险",
        description="同题材下改变职业、能力规则、代价、反派结构和阶段目标。",
        outline_constraints=(
            "不得以任何具体作品为蓝本；同类题材必须改变主角职业、能力规则、代价和第一卷目标。",
            "核心钩子至少加入两个原创变量：代价机制、使用场景、社会关系、反噬方式或道德困境。",
        ),
        chapter_constraints=(
            "不得复用具体作品的桥段排列、名场面、人物关系模板或标志性台词。",
            "常见爽文桥段必须加入原创变量，例如职业细节、误判来源、代价后果。",
        ),
        polish_constraints=(
            "检查是否只改名换皮；重点重写能力规则、第一冲突、反派动机和场景职业细节。",
            "把通用桥段改成与本书世界观/职业压力强绑定的原创事件。",
        ),
        avoid_constraints=(
            "避免复刻热门书的核心能力组合、开局事件和主角身份。",
            "避免为了贴合平台而牺牲原创变量。",
        ),
        source_refs=("StoryScope AI fiction idiosyncrasy research", "本地防撞审查规则"),
    ),
    WritingSkill(
        id="serial_feedback_arc",
        icon="📈",
        name="连载反馈与卷纲弹性",
        category="连载运营",
        description="保留主线终点，同时允许根据读者反馈强化受欢迎角色和道具。",
        outline_constraints=(
            "大纲必须有清晰开局、阶段目标和长期终点，同时保留可调整支线。",
            "配角、道具、组织和伏笔要标注可扩展性，方便连载中放大。",
        ),
        chapter_constraints=(
            "每章结尾要提供读者可讨论的问题：身份、选择、代价、关系或下一步利益。",
            "避免一次性解释完所有谜团，保留可持续讨论点。",
        ),
        polish_constraints=(
            "检查本章是否有可评论点和可追更点。",
            "把读者可能喜欢的配角/道具保留成可回收伏笔。",
        ),
        avoid_constraints=(
            "避免大纲锁死到每个细节，导致连载中无法调整。",
            "避免过早揭晓全部谜底。",
        ),
        source_refs=("Laterpress serial fiction guide",),
    ),
    WritingSkill(
        id="scene_density_dialogue",
        icon="🎬",
        name="场景密度与对白推进",
        category="正文质感",
        description="正文少解释，多用场景、动作、对白和选择推进。",
        outline_constraints=(
            "前 10 章每章至少设计 2-4 个具体场景，而不是只有剧情摘要。",
            "重要信息尽量通过冲突场景暴露，不用设定说明书。",
        ),
        chapter_constraints=(
            "正文中解释性旁白要少；优先用动作、对白、物件、环境压力展示。",
            "每 800-1200 字至少出现一次场景推进或关系变化。",
        ),
        polish_constraints=(
            "删减重复心理和说明，把信息改写进对白、动作或选择。",
            "检查对白是否有目的：压迫、试探、隐瞒、交换或反击。",
        ),
        avoid_constraints=(
            "避免连续大段设定说明。",
            "避免对白只是在互相解释读者已知信息。",
        ),
        source_refs=("通用 fiction conflict / suspense craft",),
    ),
]

DEFAULT_WRITING_SKILL_IDS = [
    "golden_three_chapters",
    "micro_conflict_loop",
    "story_bible_continuity",
    "anti_collision_originality",
    "scene_density_dialogue",
]


def skill_by_id(skill_id: str) -> WritingSkill | None:
    return next((s for s in ALL_WRITING_SKILLS if s.id == skill_id), None)


def skill_label(skill: WritingSkill) -> str:
    return f"{skill.icon} {skill.name} · {skill.category}"


def format_skill_constraints(skill_ids: list[str], scope: str) -> str:
    attr = {
        "outline": "outline_constraints",
        "chapter": "chapter_constraints",
        "polish": "polish_constraints",
        "avoid": "avoid_constraints",
    }.get(scope, "outline_constraints")
    lines: list[str] = []
    for skill_id in skill_ids:
        skill = skill_by_id(skill_id)
        if not skill:
            continue
        constraints = getattr(skill, attr)
        if not constraints:
            continue
        lines.append(f"【{skill.name}】")
        lines.extend(f"- {item}" for item in constraints)
    return "\n".join(lines).strip()


def selected_skill_names(skill_ids: list[str]) -> list[str]:
    return [s.name for sid in skill_ids if (s := skill_by_id(sid))]
