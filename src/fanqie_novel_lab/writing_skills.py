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
    WritingSkill(
        id="anti_ai_voice_texture",
        icon="🧽",
        name="降低AI味与文本纹理",
        category="正文质感",
        description="减少模板化总结、空泛形容和解释腔，增强人物口吻、具体物件和现场感。",
        outline_constraints=(
            "大纲要给每个主要人物设计可辨识口头禅、说话节奏、行为习惯或物件锚点，避免角色声音同质化。",
            "关键卖点必须绑定具体职业、场景、物件或人际关系，不只写抽象爽点。",
            "风险备注中必须检查：是否过度依赖‘震惊全场、命运齿轮、空气凝固、他不知道的是’等模板表达。",
        ),
        chapter_constraints=(
            "正文不得出现‘以下是、作为AI、根据要求、本章讲述、本章总结’等说明口吻。",
            "减少万能句式和空泛形容；每个重要情绪都用动作、物件、对白或身体反应承载。",
            "人物对白要有身份差异：职业术语、避而不答、抢话、口头习惯、误解和潜台词，不能所有人都像同一个旁白。",
            "每 1200 字至少放入一个可记住的具体细节：账单、旧伤、便签、钥匙、监控死角、气味、手势或场景物件。",
        ),
        polish_constraints=(
            "删除或改写模板化过渡句、总结句和AI式排比，让段落更像人在现场反应。",
            "把‘他很震惊/她很愤怒/气氛很紧张’改成可见动作、对白停顿、物件变化或旁人反应。",
            "检查重复词、同质化句长和过于工整的三段式表达，适当加入短句、断句和人物自己的表达习惯。",
        ),
        avoid_constraints=(
            "避免连续使用‘所有人都愣住了、全场死寂、命运齿轮开始转动、他不知道的是’这类AI高频套话。",
            "避免每章结尾只用旁白吊胃口；钩子必须落在具体证据、选择、人物动作或新风险上。",
            "避免用抽象标签代替场景，例如只写‘压迫感很强、爽点拉满、反转很炸’。",
        ),
        source_refs=("本地文本去模板化规则", "网文正文编辑经验"),
    ),
    WritingSkill(
        id="foreshadowed_reversal",
        icon="🪃",
        name="有迹可循的意外反转",
        category="钩子反转",
        description="增强出乎意料但回看合理的反转：先埋证据，再改读者理解，不靠硬拐。",
        outline_constraints=(
            "前 10 章每章的 twist 必须写清：表层误导、真实原因、提前伏笔、反转后新增问题。",
            "每个大反转至少提前埋 2 个可回看的伏笔：异常对白、物件细节、规则例外、时间差、利益矛盾或人物小动作。",
            "反转不能靠临时新增设定、空降人物、硬改人物动机完成；必须来自已出现的规则、关系或利益。",
            "卷纲要安排‘小误判—局部揭示—更大误判—阶段真相’的递进，避免一章把谜底全揭完。",
        ),
        chapter_constraints=(
            "每章至少设计一个信息差：主角知道但读者暂不知道、读者知道但角色误判、或双方都误解关键证据。",
            "反转出现前必须有一个不起眼线索；反转后要让读者意识到‘原来前面那句话/那个物件有用’。",
            "章中反转要改变局势：让优势变代价、让救援变陷阱、让敌人暴露更高层压力，不能只是换个说法。",
            "章末钩子优先落在新证据、新误判、新选择或代价兑现上。",
        ),
        polish_constraints=(
            "检查反转是否硬拐；如果读者无法回看找到线索，补 1-2 个低调伏笔。",
            "把单纯‘震惊式反转’改成‘证据重解释式反转’：同一事实在反转前后意义不同。",
            "删掉提前解释真相的旁白，保留让读者自己拼出来的线索。",
        ),
        avoid_constraints=(
            "避免为了反转突然新增规则、突然降智、突然让角色性格变脸。",
            "避免每次反转都靠陌生人登场或主角刚好听见秘密。",
            "避免伏笔过于显眼导致读者提前猜到；线索要自然嵌在冲突、物件或对白里。",
        ),
        source_refs=("Chekhov's gun / setup-payoff craft", "悬念与误导写作规则"),
    ),
    WritingSkill(
        id="hook_bank_diversity",
        icon="🪝",
        name="钩子库多样化",
        category="开篇留存",
        description="提供更多章内与章末钩子类型，避免每章都只靠空泛悬念。",
        outline_constraints=(
            "recurring_hooks 必须覆盖至少 8 种不同钩子：身份误判、利益倒挂、规则漏洞、关系背刺、证据反咬、时间倒计时、代价兑现、隐藏盟友、道德两难、承诺反噬。",
            "前 10 章不得连续两章使用同一种章末钩子；每章要标注钩子类型。",
            "钩子必须绑定主角阶段目标和现实压力，不能只是‘更大的秘密即将揭晓’。",
        ),
        chapter_constraints=(
            "从钩子库中至少选择一种用于本章：身份误判、利益倒挂、规则漏洞、关系背刺、证据反咬、倒计时、代价兑现、隐藏盟友、道德两难、承诺反噬。",
            "章末钩子要具体到一个问题、一个动作、一个证据或一个选择，让读者知道下一章要看什么。",
            "不要连续使用同一种结尾模板；如果上一章是危机升级，本章优先用证据反咬、关系反转或代价兑现。",
        ),
        polish_constraints=(
            "检查钩子是否类型单一；把空泛悬念替换为具体的证据、倒计时、选择或关系变化。",
            "强化钩子的‘下一章可兑现性’，避免只吊胃口不推进。",
        ),
        avoid_constraints=(
            "避免每章都以‘门外有人/手机响了/他不知道的是’收尾。",
            "避免只制造悬念不兑现，导致读者疲劳。",
            "避免钩子与本章冲突无关。",
        ),
        source_refs=("连载留存钩子清单", "本地章节审核规则"),
    ),
]

DEFAULT_WRITING_SKILL_IDS = [
    "golden_three_chapters",
    "micro_conflict_loop",
    "story_bible_continuity",
    "anti_collision_originality",
    "scene_density_dialogue",
    "anti_ai_voice_texture",
    "foreshadowed_reversal",
    "hook_bank_diversity",
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
