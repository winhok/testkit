---
name: testspec-review
description: TestSpec 用例评审（流程第 5 步）- 对生成的测试用例做 14 维度交叉验证（R1-R6 规则检查 + H1-H8 启发式检查），产出 review-report.md 评审报告。当用户要「评审用例」「检查用例质量」「审查测试用例」或执行 testspec-review / testspec review 时使用。也适用于用户说「用例写完了帮我看看」「检查一下覆盖度」「用例有没有问题」的场景。支持默认模式和 --deep 深度模式。
---

# testspec-review：用例评审

铁律：每项评审发现都必须注明具体范围（`case_id`、`TP_ID` 或 `GLOBAL:<rule>`）和具体修复动作。

```text
TestSpec 评审进度：

- [ ] 步骤 1：定位当前 change 目录 ⚠️ 必需
- [ ] 步骤 2：加载必需输入并执行健康检查 ⛔ 阻塞
- [ ] 步骤 3：确定 Import-Quarantine/Provenance-Unknown/Strict/Legacy 模式和评审深度
- [ ] 步骤 4：执行 R1-R6 和 H1-H8 检查
- [ ] 步骤 5：写入带证据的 review-report.md
- [ ] 步骤 6：写入反馈 context 并报告下一步
```

## 核心约束

只给可执行、可定位、可修复的结论：实体问题指向具体 `case_id` 或 `TP_ID`；解析失败、全局分布、命名字典缺失等系统性问题使用 `GLOBAL:<rule>`，并列出受影响范围和明确整改动作。

## 职责

以独立评审视角，对测试用例做 14 维度交叉验证，输出结构化 `review-report.md`，并为上游 skill 提供可落地的反馈闭环。

## 当前变更目录

参见 `../_testspec-shared/references/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 评审模板：`review-report-template.md`
- 维度细则：`references/review-dimensions.md`
- 上下文协议：`../_testspec-shared/references/context-protocol.md`
- 来源、Legacy Import 和 Oracle scope：`../_testspec-shared/references/source-provenance.md`

---

## 深度策略（统一语义）

默认执行 `auto` 模式：Agent 先判断复杂度和风险，再决定标准深度或加深深度。

- `auto`（默认）：按信号自动选择
- `--deep`（显式）：强制加深深度，不再降级

### auto 信号

**触发加深检查：**
- 用例总数 > 50
- 涉及模块数 > 5
- 同时满足用例类型 ≥ 3 且用例总数 ≥ 20
- 上游 `material_quality = low`
- 上游 `risks_identified` 非空
- 上游 `blocking_open_questions` 非空

**可保持标准深度：**
- 用例总数 ≤ 50
- 模块数 ≤ 2
- 上游 `material_quality = high/medium`
- 没有已知高风险或阻塞问题

Strict/Legacy 只决定追溯检查的置信度，不单独决定深度。多个信号冲突时，以风险信号优先；报告中列出实际触发项。

### 深度行为差异

- 标准深度：执行 14 项检查，H3 对高风险 TP 全解释
- 加深深度：执行 14 项检查，额外读取 `requirements-analysis.md`，H3 对所有 TP 全解释，H5 最低覆盖类型要求提高到 3

评审开始时必须向用户说明当前深度及理由。

---

## 输入策略

### 必读文件

- `artifacts/testcases.json`（canonical path）
- `specs/testpoints.md`

### 可选文件

- `requirements-analysis.md`（`--deep` 或 auto 加深时建议读取）

### 输入健康检查（失败即终止）

1. `artifacts/testcases.json` 存在且可解析；只有该文件不存在时才读取根目录 `testcases.json` 作为 Legacy fallback，并明确告警。两者同时存在时始终使用 artifacts 版本
2. 顶层包含 `testcases` 数组且非空
3. `specs/testpoints.md` 存在且包含 TP_ID
4. 读取 canonical source（优先 `requirements.md`，否则 `proposal.md`），按 `../_testspec-shared/references/context-protocol.md` 比较版本
5. canonical 有版本时，`specs/testpoints.md` 与 `testcases.json._context.source_revision` 都必须与 canonical 完全一致：
   - testpoints 缺少版本或版本更低 → 终止并提示先运行 `testspec-points`，之后再运行 generate
   - testcases 缺少版本或版本更低 → 终止并提示先运行 `testspec-generate`
   - 任一版本高于 canonical → 终止并报告元数据损坏
6. testpoints/testcases 版本与 canonical 相等时，即使 inherited stale 列表仍含 `review-report.md`，也允许执行本次 review；review 成功后该 stale 项被解决
7. canonical 无版本：按 Legacy 版本兼容模式继续并告警，不得仅因缺少 `source_revision` 终止

若失败：终止评审并提示先补齐上游产物（`testspec-generate` 或 `testspec-points`）。

### 模式判定

- **Import-Quarantine**：`_context.origin.kind = legacy-import` 且 `_context.trust.status = unverified`
- **Provenance-Unknown**：`_context` 或任一 case 的 `origin` / `trust` 缺失、不是对象、关键枚举为空/未知，或来源与信任组合非法/上下不一致
- **Strict**：`schema_version: 2` 且所有用例有非空 `tp_refs`
- **Legacy**：否则

模式判定优先级固定为 `Import-Quarantine > Provenance-Unknown > Strict/Legacy`。
Legacy 模式仍可评审，但 R6/H3 置信度下调，并在报告中明确升级建议。
Import-Quarantine 必须产生 `GLOBAL:legacy-traceability` S1，`review_gate.status = blocked`；评审可以继续给出修复清单，但不得伪装通过。
Provenance-Unknown 必须产生 `GLOBAL:provenance-unknown` S1，`review_gate.status = blocked`；`origin={}` / `trust={}` 不算有效 provenance。先隔离导入或从当前 PRD 重新生成。

---

## 评审维度（14 项）

执行细则、判定阈值和输出字段见 `references/review-dimensions.md`。本文件只保留最小执行索引。

### R1-R6 规则检查

1. R1 覆盖度
2. R2 命名契约
3. R3 优先级分布
4. R4 字段完整性
5. R5 可执行性最小条件
6. R6 可追溯性

### H1-H8 启发式检查

1. H1 冗余检测
2. H2 预期结果质量
3. H3 意图一致性
4. H4 前置条件充分性
5. H5 风险与边界覆盖
6. H6 可维护性建议
7. H7 回归价值评估
8. H8 测试价值与亮点识别

---

## 严重级别体系

- **S1 阻断级**：必须修复（影响可执行性或严重偏离测试意图）
- **S2 重要级**：应当修复（影响覆盖质量、追溯、维护）
- **S3 建议级**：可选优化（提升可读性和效率）

S1 只用于真正阻断问题，禁止滥用。

---

## 执行步骤

1. **定位变更目录**
2. **读取输入并做健康检查**
3. **按固定优先级判定 Import-Quarantine/Provenance-Unknown/Strict/Legacy 模式**
4. **判定深度（auto 或 --deep）并向用户说明**
5. **加载维度细则**：`references/review-dimensions.md`
6. **按 R1→R6 执行规则检查**
7. **按 H1→H8 执行启发式检查**
8. **生成报告**：按 `review-report-template.md` 填写全部结果
9. **计算总体置信度**
10. **输出总结与闭环建议**

H3/H7 必须检查组件与 Oracle 范围：`indirect` 用例不得断言下游副作用已完成，`out-of-scope` 不应成为正式用例。

---

## 报告要求

`review-report.md` 至少包含：

- 评审模式（Import-Quarantine/Provenance-Unknown/Strict/Legacy）
- 深度（标准/加深）与触发原因
- 14 项检查矩阵
- S1/S2/S3 问题列表（每条带稳定 issue ID、`open/resolved/accepted` 状态、`case_id`/`TP_ID`/`GLOBAL:<rule>`、影响和建议）
- 机器可读 `review_gate`：`status`、`s1_unresolved_count`、`s1_issue_ids`
- 总体结论（通过/有问题）
- 置信度（高/中/低）

---

## 反模式识别

| 反模式 | 表现 | 修正 |
|--------|------|------|
| 走形式检查 | 全部“通过”但无证据 | 每项至少给 1 个量化指标 |
| 模糊建议 | “建议优化”“需要改进” | 明确到字段和修改动作 |
| 遗漏范围 | 问题无 case_id/TP_ID/全局规则 | 实体问题绑定 ID；系统问题使用 `GLOBAL:<rule>` 并列受影响范围 |
| 比例至上 | 只看占比不看内容 | 先核实关键场景是否真实覆盖 |
| 忽视上游 | 不消费风险/阻塞澄清信息 | 强制读取上游 context |
| 过度报告 | 把细节问题都标 S1 | 严格按分级定义降噪 |

---

## 总体置信度

- **高**：Strict + 输入完整 + 14 项均可执行
- **中**：Legacy，或部分检查依赖推断
- **低**：输入缺失，导致关键检查无法执行

---

## 反馈合成闭环

评审完成后必须给出三类结构化反馈：

### 给 generate

- 需要补充哪些 TP 场景
- 哪些用例字段要改（`id`、`title`、`steps`、`expected_result`、`tp_refs` 等）
- 策略层建议（如冒烟过宽/过窄）

### 给 points

- 哪些 TP 粒度过粗/过细
- 哪些 TP 缺失导致覆盖断层

### 给 analysis

- 新发现的需求缺口
- 上游未标注但已在评审中暴露的风险

### 上下文播种

在 `review-report.md` 末尾按 `../_testspec-shared/references/context-protocol.md` 写入：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-review",
  "canonical_source_policy": "prd-first",
  "evidence_sources": [{"type": "<prd/api/ui/code/testlib>", "source_ref": "<从上游继承>", "authority": "<canonical/reference>"}],
  "questions": [{"id": "Q-001", "status": "<open/resolved/invalidated/deferred>", "blocking": true, "question": "<从上游继承>", "resolution": ""}],
  "source_revision": {"version": "<canonical 版本>", "summary": "<原样继承>", "updated_by_skill": "<原样继承>"},
  "blocking_open_questions": ["<从上游继承>"],
  "dynamic_followups": ["<从上游继承>"],
  "material_quality": "<从上游继承>",
  "stale_downstream_artifacts": [],
  "review_gate": {
    "status": "pass/blocked",
    "s1_unresolved_count": 0,
    "s1_issue_ids": []
  },
  "risks_identified": ["<评审中新发现的风险>"],
  "feedback_for_generate": ["<给 generate 的结构化反馈>"],
  "feedback_for_points": ["<给 points 的结构化反馈>"],
  "feedback_for_analysis": ["<给 analysis 的结构化反馈>"]
}
-->
```

---

## 输出总结模板

```text
✅ 评审完成 | 模式: <Import-Quarantine/Provenance-Unknown/Strict/Legacy> | 深度: <标准/加深> | 置信度: <高/中/低>
📄 报告: testspec/changes/<name>/review-report.md
📊 总评: <S1> 个 S1 + <S2> 个 S2 + <S3> 个 S3
```

## 产物

- `testspec/changes/<name>/review-report.md`
