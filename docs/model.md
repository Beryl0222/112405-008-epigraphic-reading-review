# 领域模型、依赖链与复核状态

本文件说明 `case_workbench` 如何把题目中的业务要求落成可检查的结构。
所有记录都是 `data/workbench.json` 中带 `id/type/status/history` 的普通 dict。

## 1. 记录类型

| 集合 | 类型 | 说明 |
| --- | --- | --- |
| `sources` | `source` | 原始来源记录，如 `data/case.json` 的 EP-1/2/3，原文稳定保留 |
| `people` | `person_record` | 释读者、编目员、研究者（合成人物） |
| `glyphs` | `glyph_position` | 字形位置：所属器物/拓片、行、列、坐标、位置说明、有序候选 `candidates` |
| `opinions` | `opinion` | 历次释读意见：专家、所读字、把握程度、`basis[]`、来源 EP、状态 |
| `evidence` | `evidence` | 证据：拓本/照片/目验/考古背景/独立文本/材质测年；照片与拓本只是字形证据 |
| `artifacts` / `rubbings` | `artifact` / `rubbing` | 器物（含别名、误建合并状态）与拓片说明 |
| `sites` / `lineages` | `site` / `lineage` | 出土地点与家族谱系 |
| `persons` / `mentions` / `identity_rules` | 谱系人物 / 名号出现 / 条件同一规则 | 支撑合并/分开推演 |
| `catalogs` / `adoptions` | 编目卡 / 释读采纳 | 采纳把“某卡某字形”明确系于一条有效意见，并快照依据 |
| `date_claims` / `events` | 年代说法 / 事件主张 | 年代可成为关系端点；事件另有独立的真实性状态 |
| `relations` | `relation` | 七类关系，见下 |
| `citations` | `citation` | 研究引用，可同时指向多条关系/采纳 |
| `audit` | 审计条目 | 跨集合动作日志（撤回、合并、照片边界、级联结果等） |

`relations.kind`：

- `unearthed_at` / `found_at`：器物—出土地/采集地；
- `assigned_to_lineage`：器物—家族谱系；
- `same_identity`：名号—谱系人物同一；
- `kinship`：人物—人物亲属；
- `dated_to`：器物—年代说法；
- `alludes_to_event`：铭文—所述事件关联。

## 2. 每条关系如何携带“采用了哪种释读及可信依据”

`add_relation(..., adoption_id=..., opinion_id=..., candidate=..., basis=...)`
会在关系上写入不可变的 `reading` 快照：

```json
{
  "glyph_id": "G-6",
  "candidate": "周",
  "opinion_id": "OP-3",
  "adoption_id": "ADP-1",
  "expert_name": "释读者乙（合成人物）",
  "confidence": "medium",
  "basis": [ {"kind": "glyph-shape", "detail": "……"} ],
  "opinion_status": "active"
}
```

`relation_view()` 还会补充意见与采纳的**实时**状态
（`opinion_current_status`、`adoption_current_status`），因此撤回后查询会亮警示，
而不必相信快照里的旧状态。

三条防“静默定论”规则：

1. 采纳的意见必须处于 `active`；已撤回/已取代的意见不能被采纳；
2. 直接写 `candidate` 时，该字必须已在字形的 `candidates` 中，且必须给显式依据，
   并标记 `hypothesis_only=true`；
3. 同一编目卡+字形只允许一个 active 采纳；改采会把旧采纳置为 `superseded`，
   依赖旧采纳的关系进入待复核，而不是被悄悄改写。

## 3. 依赖链与撤回级联

```
opinion ──< adoption ──< relation ──< citation
   └──────────────────< relation（直接引用 opinion 的情况）
artifact(merge) ──────< relation
```

专家撤回 `OP-x`（`withdraw_opinion`）后，`reconcile_review_state()` 做全量对账：

1. 意见置 `withdrawn`（写 `withdrawn_at/by/reason` 与历史，不删除）；
2. 采纳若指向被撤回意见 → 增加 `opinion-withdrawn:OP-x` 问题并置 `pending_review`；
3. 关系若直接依据该意见、或依据待复核/被取代的采纳 → 增加对应依赖问题并置待复核；
   器物合并改指产生的 `artifact-merge:A-x` 问题同理；
4. 引用的任一目标待复核 → 增加 `target-pending:T` 问题并置待复核。

`withdraw_opinion()` 返回 `newly_pending` 清单，精确列出“本次撤回新波及”的
采纳/关系/引用；本来就待核的记录不会被重复计数。

### 问题分类与恢复

- `dependency` 问题：依赖恢复后可由 `reconfirm` 关闭；
- `scholarly` 问题（如 EP-3 自陈“待核”）：即使依赖更新也保持打开，
  必须 `acknowledge_scholarly=True` 且给出实质 `note` 才能关闭。

恢复顺序是自下而上的：编目改采有效新意见（新 `ADP`）→
`reconfirm(relation, new_adoption_id=...)` → 对账会自动恢复全部目标已健康的引用；
也可显式 `reconfirm(citation)`，但若目标仍待复核会直接报错。

状态不会被对账冲掉：`superseded/withdrawn/retracted/merged_duplicate`
等生命周期状态优先于“无待办问题即 active”的计算。

## 4. 同名人合并/分开（条件身份规则 + 并查集）

`identity_rules` 形如：

```json
{"id": "IR-1", "mention_id": "MN-1", "person_id": "P-ZB",
 "glyph_id": "G-6", "if_reading": "周", "via_opinion_id": "OP-3"}
```

`Workbench.resolve_persons(overrides=None)`：

- 不传 `overrides`：使用每个字形当前唯一的 active 采纳；无采纳或采纳待复核时
  规则判定为 `pending`（不强行合并也不强行分开）；
- 传 `{"G-6": "舟"}` 等：做只读 what-if，不触碰库内编目结论；
- 判定为 `merged/unconditional` 的端点进同一并查集簇；不同候选读法则 `split`；
  若其他规则已把“应分开”的两端合并，输出 `conflicts` 交人工审定。

## 5. 证据边界：照片 ≠ 事件发生

- `add_photo()` 只写一条 `kind="photo"` 的 `evidence`、字形历史与
  `photo_evidence_only` 审计；没有任何代码路径会修改 `events.occurrence_status`；
- `corroborate_event()` 只接受
  `archaeological-context / independent-text / material-dating`
  或显式 `independent=true` 的证据；照片、拓本、释读意见一律抛 `ValidationError`；
- 即便字形读法把握提高到 `high`，事件状态仍保持 `unverified`，直到另有独立证据。

## 6. 器物身份与重复拓片

- 器物有主 `id` 与 `aliases`（旧号、新号、登记号）；
- 后到拓片被误建成新器物时，不删除该器物，而是
  `status=merged_duplicate, duplicate_of=canonical`；
- `merge_artifacts()` 把拓片、编目卡、关系端点改指 canonical，登记别名，
  逐实体写 `artifact_repointed/endpoint_repointed` 历史，并给改指关系挂
  `artifact-merge:<id>` 待复核问题，再向上同步引用状态。

## 7. 持久化

单个 UTF-8 JSON 文件即整个库（`Workbench.save/load`，保存时 tmp+replace 原子替换）。
`research_report()` 输出可直接给前端/脚本消费的稳定 dict（`--json` 即其序列化）。
