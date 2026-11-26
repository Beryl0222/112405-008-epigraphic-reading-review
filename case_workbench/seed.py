"""构造合成案例库。

时间线（全部名称、编号、地点、人物均为演练用合成样本）：

- EP-1/2/3 是 ``data/case.json`` 中的稳定原始记录，原样保留；
- 释读者甲、乙先后给出“舟/周”意见；
- 编目员壬据 OP-3（周）建卡、采纳，并把 E12 并入周氏谱系；
- 新照片 EVD-PH1 只增加字形证据，甲据此再提 OP-4；
- 后来的拓片 RB-2 曾被误建为新器物 ART-E999，随后被合并纠正；
- 研究札记 CITE-1 引用了由此产生的谱系、身份、亲属与年代关系。

撤回 OP-3 的脚本化演练见 ``scenario.py``。
"""

from __future__ import annotations

from pathlib import Path

from .models import PENDING_REVIEW, TENTATIVE
from .workbench import Workbench

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_JSON = PROJECT_ROOT / "data" / "case.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "workbench.json"


def build_workbench(case_json_path: str | Path | None = DEFAULT_CASE_JSON) -> Workbench:
    wb = Workbench()
    if case_json_path is not None:
        wb.load_case_json(case_json_path)

    # ------------------------------------------------------------ 人员
    wb.add_person("U-JIA", "释读者甲（合成人物）", role="paleographer")
    wb.add_person("U-YI", "释读者乙（合成人物）", role="paleographer")
    wb.add_person("U-REN", "编目员壬（合成人物）", role="cataloger")
    wb.add_person("U-GUI", "研究者癸（合成人物）", role="researcher")

    # ------------------------------------------------- 器物 / 拓片 / 字形位置
    wb.add_artifact(
        "ART-E12",
        "E12号残铭铜器（合成）",
        registration_no="E12",
        aliases=["E-12"],
        note="EP-2：器号 E-12 与 E12 为同一件器物的旧、新登记号。",
    )
    wb.register_alias("ART-E12", "E-12（旧号）")
    wb.add_artifact("ART-E07", "E07号残铭铜器（合成）", registration_no="E07")
    wb.add_artifact(
        "ART-E999", "被误判为新器物的拓本对象（合成）",
        registration_no="E999",
        note="收到 RB-2 拓片时 intake 误建；后由编目员判定为 E12 的后拓本。",
    )

    wb.add_rubbing(
        "RB-1", "E12铭文初拓本（合成）", artifact_id="ART-E12",
        description="拓片第6行有缺损字，右侧存残笔；对应 EP-1。",
        source_record_id="EP-1",
    )
    wb.add_rubbing(
        "RB-E07", "E07铭文拓本（合成）", artifact_id="ART-E07",
        description="含可与谱系‘周伯’名号对读的合成铭文片段。",
    )
    wb.add_rubbing(
        "RB-2", "E12后拓本（合成，曾被误当成新器物 E999）", artifact_id="ART-E999",
        description="更晚近的拓本，行款与 RB-1 相合；intake 时被挂在误建的 ART-E999 下。",
        later_rubbing=True,
    )

    wb.add_glyph(
        "G-6",
        "E12拓片第6行缺损字",
        artifact_id="ART-E12",
        rubbing_id="RB-1",
        line=6,
        column=None,
        coordinates={"line": 6, "bbox_synthetic": [120, 340, 152, 372]},
        note="EP-1：暂释‘舟’，右侧残笔也可能为‘周’。字形位置必须与候选读法一起保留。",
        candidates=["舟", "周"],
    )

    # ------------------------------------------------------------ 证据与意见
    wb.add_evidence(
        "EVD-RB1", "rubbing", "初拓本残笔证据（合成）",
        glyph_id="G-6",
        observed_traits=["字口漫漶", "残存右侧竖向笔势", "可见两处短画残痕"],
        source_ref="RB-1 / EP-1",
        added_at="2024-05-10T09:00:00+00:00",
    )
    wb.add_opinion(
        "OP-1", "G-6", "舟", expert_id="U-JIA", confidence="provisional",
        expressed_at="2024-05-10", source_record_id="EP-1",
        note="EP-1 中的暂释",
        basis=[
            {"kind": "context", "detail": "依残存辞例暂拟为‘舟’，仅为临时读法。"},
            {"kind": "rubbing", "detail": "EVD-RB1：拓本文字漫漶，不足以排除其他读法。",
             "evidence_id": "EVD-RB1"},
        ],
    )
    wb.add_opinion(
        "OP-2", "G-6", "周", expert_id="U-JIA", confidence="low",
        expressed_at="2024-05-10", source_record_id="EP-1",
        note="EP-1 同时保留的候选",
        basis=[
            {"kind": "glyph-shape", "detail": "右侧残笔走向与‘周’字外廓有相似处，但残损过甚。",
             "evidence_id": "EVD-RB1"},
        ],
    )
    wb.add_opinion(
        "OP-3", "G-6", "周", expert_id="U-YI", confidence="medium",
        expressed_at="2024-09-02",
        basis=[
            {"kind": "glyph-shape", "detail": "右侧竖笔与横折残画可与‘周’字外围对应（合成字形分析）。"},
            {"kind": "comparison", "detail": "与三件合成拓本中的‘周’形并列比较，轮廓相合。"},
            {"kind": "rubbing", "detail": "EVD-RB1 残笔位置测量与第6行行宽一致。",
             "evidence_id": "EVD-RB1"},
        ],
    )

    # 新照片：只增加可见字形证据，并产生新意见 OP-4；不改变任何事件状态。
    wb.add_photo(
        "EVD-PH1", "E12红外补光照（合成照片）", glyph_id="G-6",
        observed_traits=["右侧竖向残笔更清晰", "两横向断笔与‘周’内横位置相近",
                         "未见可确证为‘舟’的撇画残痕"],
        source_ref="PH-NEW-1（合成影像，无真实文件）",
        added_at="2025-01-18",
    )
    wb.add_opinion(
        "OP-4", "G-6", "周", expert_id="U-JIA", confidence="medium",
        expressed_at="2025-02-01",
        note="照片后仍非定论：残字关键笔画缺失，‘舟’读未被完全排除。",
        basis=[
            {"kind": "photo", "detail": "EVD-PH1 显示的竖笔与两横残痕支持‘周’的候选。",
             "evidence_id": "EVD-PH1"},
            {"kind": "glyph-shape", "detail": "未见‘舟’字应有的撇画，但缺损区域恰好覆盖该位置，不能据此反证。"},
        ],
    )

    # ------------------------------------------------------------ 出土地点
    wb.add_source(
        "SRC-EXC-1",
        "（合成）采集与出土记录：E12 于河东塬遗址灰坑 H7 采集，同出陶片为合成标本。",
        kind="excavation-record", source="合成考古记录",
    )
    wb.add_site("SITE-HD", "河东塬遗址（合成地名）",
                note="E12 的采集/出土地判断依据 SRC-EXC-1。")
    wb.add_site("SITE-NB", "北岸祭祀遗存（合成地名）",
                note="仅因 EP-3‘北岸祭祀记录’被联想，尚无证据把 E12 出土地系联于此。")

    # ------------------------------------------------------------ 谱系与人物
    wb.add_lineage("LIN-ZHOU", "周氏宗族谱系（合成谱系资料）",
                   note="馆藏人员据‘周’读把 ART-E12 并入该谱系。")
    wb.add_person_entity("P-ZH", "周侯（合成谱系先辈）", lineage_id="LIN-ZHOU")
    wb.add_person_entity("P-ZB", "周伯（合成谱系人物）", lineage_id="LIN-ZHOU",
                         note="谱系中周侯下一辈；是否与 E12 名讳为同一人取决于 G-6 读法。")

    wb.add_mention(
        "MN-1", "E12第6行名讳（舟/周两读）",
        artifact_id="ART-E12", glyph_id="G-6",
        note="读作‘周’时与‘周伯’名号相合；读作‘舟’时是另一个名号。",
    )
    wb.add_mention(
        "MN-2", "E07铭文中的‘周伯’称谓（合成，较清晰）",
        artifact_id="ART-E07",
        note="此前已与谱系 P-ZB 无条件比对为同一人。",
    )
    wb.add_identity_rule(
        "IR-1", "MN-1", "P-ZB",
        glyph_id="G-6", if_reading="周", via_opinion_id="OP-3",
        basis=[{"kind": "name-comparison",
                "detail": "唯当 G-6 读作‘周’，E12 名讳方与‘周伯’重合；若读‘舟’则必须分开。"}],
    )
    wb.add_identity_rule(
        "IR-2", "MN-2", "P-ZB",
        basis=[{"kind": "genealogy-comparison", "detail": "E07 称谓较清晰且有辞例支持，无条件并入 P-ZB。"}],
    )

    # ------------------------------------------------------------ 编目与采纳
    wb.add_catalog(
        "CAT-1", "ART-E12", "E12 残铭铜器编目卡（合成）",
        cataloger_id="U-REN",
        fields={"旧器号": "E-12", "新登记号": "E12", "品名（暂定）": "E12号残铭铜器"},
    )
    wb.adopt_reading(
        "ADP-1", "CAT-1", "G-6", "OP-3", by="U-REN", at="2024-10-08",
        note="编目时采纳乙的‘周’读；OP-1/OP-2 候选与意见仍完整保留。",
    )
    wb.add_catalog(
        "CAT-2", "ART-E07", "E07 残铭铜器编目卡（合成）", cataloger_id="U-REN",
    )

    wb.add_date_claim(
        "DATE-E12", "西周早期（合成年代说法，非确定结论）", artifact_id="ART-E12",
        basis=[{"kind": "typology", "detail": "器形与纹饰比照合成标本所得，独立于文字读法之外另有类型学依据。"}],
    )
    wb.add_event_claim(
        "EV-SAC", "北岸祭祀记录所指的祭祀事件（合成）",
        source_record_id="EP-3",
        note="EP-3：若读作‘周’，或与北岸祭祀记录相关，待核。事件真实性至今无独立证据。",
    )

    # ------------------------------------------------------------ 关系
    wb.add_relation(
        "REL-SITE", "unearthed_at", "ART-E12", "SITE-HD",
        certainty="confirmed", by="U-REN", at="2024-10-08",
        basis=[{"kind": "excavation-record", "detail": "SRC-EXC-1 记载 H7 采集与同出陶片。",
                "source_id": "SRC-EXC-1"}],
        source_record_ids=["SRC-EXC-1"],
    )
    wb.add_relation(
        "REL-LIN", "assigned_to_lineage", "ART-E12", "LIN-ZHOU",
        adoption_id="ADP-1", certainty="probable", by="U-REN", at="2024-10-08",
        scope="把器物并入周氏家族谱系",
        basis=[{"kind": "genealogy-comparison", "detail": "按 ADP-1 的‘周’读与谱系排比。"}],
    )
    wb.add_relation(
        "REL-ID", "same_identity", "MN-1", "P-ZB",
        adoption_id="ADP-1", certainty="probable", by="U-REN", at="2024-10-08",
        scope="E12 名讳与周伯为同一人",
        basis=[{"kind": "name-comparison", "detail": "对应条件规则 IR-1。"}],
    )
    wb.add_relation(
        "REL-KIN", "kinship", "P-ZB", "P-ZH",
        adoption_id="ADP-1", certainty="probable", by="U-REN", at="2024-10-08",
        scope="谱系内部父子关系；唯当 REL-ID 成立时，该亲属关系才及于 E12 器主。",
        basis=[{"kind": "genealogy", "detail": "合成周氏谱系载周伯为周侯晚辈。"}],
    )
    wb.add_relation(
        "REL-DATE", "dated_to", "ART-E12", "DATE-E12",
        adoption_id="ADP-1", certainty="probable", by="U-REN", at="2024-10-08",
        scope="研究札记引用的年代结论",
        basis=[{"kind": "typology", "detail": "类型学断代与‘周’读互相配合，但并非仅凭释读得出。"}],
    )
    wb.add_relation(
        "REL-EVENT", "alludes_to_event", "ART-E12", "EV-SAC",
        adoption_id="ADP-1", certainty=TENTATIVE, by="U-GUI", at="2025-03-01",
        scope="EP-3 提出的研究联想：‘周’读或与北岸祭祀记录相关",
        source_record_ids=["EP-3"],
        status=PENDING_REVIEW,
        review_issues=[{
            "code": "ep3-unverified",
            "kind": "scholarly",
            "reason": "EP-3 自陈‘待核’：除铭文自身外缺少独立证据，不能把祭祀事件当作已发生事实。",
            "by": "U-GUI",
        }],
    )

    # --------------------------------------------- 误建新器物 -> 合并纠正
    # 误建后曾匆忙给出的出土地联想（合并后进入待复核，由编目员判断）。
    wb.add_relation(
        "REL-E999-SITE", "unearthed_at", "ART-E999", "SITE-NB",
        certainty=TENTATIVE, by="U-REN", at="2025-05-09",
        basis=[{"kind": "association",
                "detail": "仅因‘周—北岸祭祀’联想临时系联，没有出土地记录。"}],
    )
    wb.merge_artifacts(
        "ART-E999", "ART-E12", by="U-REN", at="2025-06-02",
        reason="RB-2 行款、第6行残字位置与 RB-1 完全对应，且 E-12/E12 新旧号已核实；"
               "RB-2 是 E12 的后拓本而非新器物。",
    )

    # ------------------------------------------------------------ 引用
    wb.add_citation(
        "CITE-1", "研究者癸（合成人物）", "合成研究札记《E12读札》HR-1",
        ["REL-LIN", "REL-ID", "REL-KIN", "REL-DATE"],
        statement="据第6行‘周’读，将 E12 列为周氏周伯之器、周侯子辈，年代取西周早期说。",
        at="2025-03-10",
    )
    wb.add_citation(
        "CITE-2", "研究者癸（合成人物）", "合成馆藏地望小记 HR-2",
        ["REL-SITE"],
        statement="据 SRC-EXC-1 称 E12 出于河东塬 H7。该结论不依赖舟/周之辨。",
        at="2025-03-12",
    )
    wb.add_citation(
        "CITE-3", "研究者癸（合成人物）", "北岸祭祀联想稿 HR-3（未刊）",
        ["REL-EVENT"],
        statement="若‘周’读成立，或可与北岸祭祀记录相联系；作者自注待核。",
        at="2025-03-15",
    )

    wb._audit("seed_built", "合成案例库构造完成（含原始 EP 记录与完整时间线）")
    return wb
