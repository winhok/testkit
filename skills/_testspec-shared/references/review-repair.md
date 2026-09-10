# Review 定向返修

只在消费 review feedback 或处理其下游失效时加载。复用 context v2，不改变 canonical revision；产品规则变化交 testspec-update。返修记录不能替代正文变更和独立复评。

## 开始与路由

1. 先通过直接上游的 context chain/question 门禁（analysis 检查 canonical）；核对 review 的 source_revision 与 canonical 完全一致。过期 review 仅作参考，先重建并复评，不自动套用旧修复。
2. 将 review-report.md 原字节保存到 change 内新的 `artifacts/reviews/<sha256>.md`。已存在时只核对相同摘要，不覆盖。保留原报告中的 open 状态，后续复评写当前 review-report.md。
3. 仅处理本阶段 feedback 数组中的 open finding。不同阶段的问题按 analysis → plan（required）→ points → generate 顺序处理，不能用改用例掩盖上游问题。上游已发生变化时先复核旧反馈是否仍适用；不适用的留给 review 裁定。

每条 feedback 对象使用稳定 `issue_id`、`status=open/resolved/accepted`、`severity=S1/S2/S3`、`target_stage=analysis/points/generate`、`scope`（非空字符串数组）和 `action`（具体修改指令）。实体 scope 使用需求引用、TP_ID 或 case ID。缺失实体/全局问题使用 `GLOBAL:<rule>`，action 必须限定需求、模块及允许新增的内容；不能把 GLOBAL 当成全量重写许可。旧字符串反馈先由 review 转为可定位对象，不猜测分配或 ID。

issue_id 在三类反馈中全局唯一；一个问题只分配一个负责阶段，需要不同阶段独立修复时拆成不同问题。resolved 的 resolution 写复核证据位置；accepted 的 resolution 写用户接受风险的决定依据。复评保留所有已返修 issue ID，不因已修复而删除；review_gate 的 s1_issue_ids 按 ID 排序，只列 open S1，数量与 status 一致。

## 修改与收据

- analysis 修复风险、遗漏和分析结论；保留原需求引用，新增产品 decision 保持未决，不能改 canonical。
- points 保留未变 TP_ID；拆分/合并/新增/删除在摘要中记录旧新 ID 对应及需求依据，避免重排全部编号。
- generate 定向修复现有 case；上游 TP 改变时按受影响 TP 再生成，新增用例使用新 ID，保留不受影响内容。
- 修复后在本阶段 context 的 `review_repairs` 追加收据。同一评审摘要+issue_id 只记一次；重复运行先核查已完成动作，后续新评审可使用相同 issue_id 和新的快照摘要。

```json
{
  "issue_id": "RV-S1-001",
  "target_stage": "points",
  "source_review": {"path": "artifacts/reviews/<sha256>.md", "sha256": "<review 原字节 SHA-256>"},
  "changed_tp_ids": ["TP_AUTH_LOGIN_002"],
  "summary": "按 REQ-001 补充会话失效覆盖，保留已有登录 TP"
}
```

analysis 使用 `changed_requirement_refs`，generate 使用 `changed_case_ids`，均为非空且无重复的 ID 数组。非 GLOBAL finding 的变更 ID 必须属于 scope；新增/删除 ID 也记录。未实际修改不写修复收据；说明原因并交 review 处理，不自行写 resolved/accepted。

## 下游失效与验证

analysis 返修标记 strategy（required 时）、points、cases、review stale；points 标记 cases、review；generate 标记 review。保留其他已有下游 stale 项，清除本阶段项。strategy skipped 时不标记或消费遗留 strategy.md。stale_reason 写 issue IDs，next_skill 指向最早应重跑的阶段。

每次产物重建都在其 context 写 `upstream_sha256`，绑定直接上游文件的最终字节；不要向下游复制本阶段收据。已有收据在同 revision 内保留，使后续普通重生成也继续校验链。下游必须重新核对内容才能刷新摘要，不能以 revision 未变或摘要已补齐声称完成返修。

```sh
python <skills>/_testspec-shared/scripts/validate_context_chain.py --change-dir <change> --through <analysis|points|generate|review>
```

该命令校验收据归属、open 状态、范围、快照摘要及直接上游摘要；不证明自然语言修改已满足问题。返修后依序重建 stale 产物并复评，由 testspec-review 逐 issue 核查修改与证据、保留历史 ID，再更新状态和 gate。
