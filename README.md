# 古文字释读异文与馆藏关系审定工作台

一个**零第三方依赖**的 Python 3.11+ 项目，用来承接：

- 拓片说明与后到照片/拓本；
- 文字学审阅者的字形位置、候选读法与历次释读意见；
- 已有编目记录、旧/新器号、误建器物的合并纠正；
- 编目人员对“器物—出土地”“器物—谱系”关系的判断与依据；
- 研究用户查询：每条关系**采用了哪种释读、依据是什么、当前是否待复核**；
- “舟/周”异文导致的同名人**合并或分开**；
- 专家撤回意见后，采纳、关系、引用**级联进入待复核**，且全部历史保留。

> **资料性质声明**：`data/case.json` 与 `data/workbench.json` 以及代码中的
> 人物、机构、地点、器号、谱系、年代、事件全部是**合成演练样本**，不对应真实
> 对象或业务决定。第 6 行残字**没有唯一确定释文**，“舟”“周”始终都是保留中的
> 候选读法；系统不会、也不允许把某一种候选静默改写成定论。

## 快速验证

```sh
# 1) 单元测试（README 原有命令，仍然适用）
python3 -m unittest discover -s tests -v

# 不带 -s tests 的默认发现方式同样可用（tests/__init__.py 已提供）
python3 -m unittest discover

# 2) 端到端场景核验（28 个业务核验点，退出码 0/1）
python3 verify.py
# 或
python3 -m case_workbench verify
```

## 命令行用法

```sh
# 构造合成案例库并写入 data/workbench.json
python3 -m case_workbench init            # 根目录也可：python3 main.py init

# 在内存中跑完整演示（新照片→撤回 OP-3→级联待复核→改采 OP-4→复核恢复）
python3 -m case_workbench demo

# 研究报告：原始记录、候选/意见、每条关系的读法与依据、人物簇、事件、待复核清单
python3 -m case_workbench query

# “若第 6 行读作舟/周”的假设推演（只读，不改变编目结论）
python3 -m case_workbench persons --what-if 舟
python3 -m case_workbench query   --what-if 周
python3 -m case_workbench query   --json          # 完整机器可读报告

# 指定自己的 JSON 库
python3 -m case_workbench --db /path/to/lib.json query

# 只读 HTTP 查询接口（标准库；/api/report、/api/persons、/health）
python3 -m case_workbench serve --port 8765
curl "http://127.0.0.1:8765/api/report?what_if=%E8%88%9F"   # 假设“舟”
```

`data/workbench.json` 是 `init` 生成的一份现成库（撤回发生前的有效编目状态），
可直接打开核对全部字段与历史。

## 30 秒 Python API 概览

```python
from case_workbench.seed import build_workbench
from case_workbench import Workbench

wb = build_workbench()                 # 含 data/case.json 的 EP-1/2/3 原始记录

# 文字学审阅者：位置 + 候选 + 历次意见
wb.add_glyph("G-X", "某拓本第X行残字", line=6, coordinates={"x": 12, "y": 30},
             candidates=["舟", "周"])
wb.add_opinion("OP-X", "G-X", "周", expert_id="U-YI", confidence="medium",
               basis=[{"kind": "glyph-shape", "detail": "右侧残笔……"}])

# 编目：采纳必须指向有效意见，并快照其依据
wb.adopt_reading("ADP-X", "CAT-1", "G-X", "OP-X", by="U-REN")

# 研究：每条关系采用的读法 + 可信依据 + 实时状态
report = wb.research_report()

# 同名人合并/分开：当前编目读法，或传假设读法做 what-if
wb.resolve_persons({"G-6": "舟"})      # -> IR-1 split
wb.resolve_persons()                   # -> 按 ADP-1(周) -> merged

# 新照片只增加可见字形证据；事件真实性状态保持 unverified
wb.add_photo("EVD-N", "新照片", glyph_id="G-6", observed_traits=["……"])

# 专家撤回：意见 -> 采纳 -> 关系 -> 引用 级联 pending_review，只追加历史不删除
print(wb.withdraw_opinion("OP-3", by="U-YI", reason="依据表述过强"))

# 改采新意见并自下而上复核恢复
wb.adopt_reading("ADP-2", "CAT-1", "G-6", "OP-4", by="U-REN")
wb.reconfirm("REL-LIN", by="U-REN", new_adoption_id="ADP-2", note="核对后维持")

wb.save("data/workbench.json")
Workbench.load("data/workbench.json")
```

## 目录结构

```
data/case.json             # 题目给定的稳定原始记录 EP-1/2/3（不修改）
data/workbench.json        # `init` 生成的完整合成库（可删后重建）
case_workbench/
  models.py                # 状态常量、证据类别、统一声明
  errors.py                # 领域异常
  identity.py              # 并查集 + 条件身份规则（合并/分开/待定，纯逻辑）
  workbench.py             # Workbench：登记/采纳/关系/引用/撤回级联/复核/持久化/查询
  seed.py                  # 合成案例时间线（舟/周、E-12/E12、E999 误建、北岸事件…）
  scenario.py              # 端到端脚本与 28 个核验点
  cli.py / __main__.py     # 命令行
tests/                     # 53 个 unittest 用例（含原始 test_materials.py 与 HTTP 接口）
verify.py                  # 仓库级端到端验证
docs/model.md              # 领域模型、依赖链与状态机说明
```

## 关键不变量（项目如何回应每条要求）

| 要求 | 落地机制 | 主要测试 |
| --- | --- | --- |
| 保留字形位置与候选读法 | `glyphs` 存行/列/坐标/位置说明与有序 `candidates`；新意见可追加候选但绝不覆盖 | `test_readings_and_adoption.py` |
| 历次释读意见不丢失 | `opinions` 仅追加；含专家、时间、把握程度、依据、来源 EP 编号；撤回只改状态 | 同上、`test_withdrawal_cascade.py` |
| 编目不能把不确定释读静默改成定论 | 采纳必须指向**有效**意见并快照依据；直接写候选必须在候选列表内且给显式依据，否则 `ValidationError`；候选与意见始终可查 | `test_readings_and_adoption.py` |
| 旧号 E-12 / 新号 E12 同一器物 | 别名表 + `find_artifact/resolve_artifact_id` | `test_artifacts_and_sites.py` |
| 后到拓片被误当新器物 | 误建器物保留为 `merged_duplicate → canonical`，拓片/编目/关系改指并留历史；受影响关系进待复核 | 同上 |
| 编目判断器物—出土地关系 | `unearthed_at` 关系 + 依据（如 `SRC-EXC-1` 出土记录），与释读解耦，撤回意见不影响它 | 同上、`test_withdrawal_cascade.py` |
| 查询看到每条关系的读法与可信依据 | `research_report()/relation_view()` 给出 reading 快照、依据条数、意见实时状态、待复核问题、被哪些引用使用 | `test_research_query.py` |
| 异文导致同名人合并/分开 | 条件规则 `if_reading="周"`；当前采纳→合并，what-if 舟→分开，无有效采纳/意见撤回→待定；并查集出人物簇 | `test_identity.py` |
| 新照片只改变可见字形证据 | `add_photo` 只写 `evidence` 与字形历史/审计；不存在照片→事件状态的代码路径 | `test_evidence_boundary.py` |
| 照片不能自动证明事件发生 | 事件独立维护 `occurrence_status=unverified`；用照片/拓片/意见去 `corroborate_event` 一律拒绝；只有考古背景/独立文本/材质测年等独立证据可走显式佐证 | 同上 |
| 撤回意见→目录与引用待复核且不丢历史 | 依赖链 `opinion → adoption → relation → citation` 全量对账，置 `pending_review` 并追加问题与状态历史；无硬删除；可改采+复核恢复 | `test_withdrawal_cascade.py` |
| 学术“待核”不被复核流程顺手清掉 | 问题分 `dependency` 与 `scholarly`；后者必须 `acknowledge_scholarly=True` 且给实质说明才能关闭 | 同上 |
| 全部为合成样本、无确定释文答案 | `DATA_NOTICE` 注入每份报告/CLI/JSON；种子与命名均标注“合成” | 多处断言 |

## 依赖与运行环境

- Python ≥ 3.11（开发与验证使用 Python 3.11.2）；
- 无第三方运行/测试依赖，仅标准库；
- `python3 -m unittest`、`python3 verify.py`、`python3 main.py` 均支持从任意
  工作目录调用（入口会自行处理 `sys.path`），在 `python3 -I` 隔离模式下同样通过。
