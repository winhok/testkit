---
name: testspec-review
description: TestSpec 用例评审（流程第 5 步）- 对生成的测试用例做 14 维度交叉验证（R1-R6 规则检查 + H1-H8 启发式检查），产出 review-report.md 评审报告。当用户要「评审用例」「检查用例质量」「审查测试用例」或执行 testspec-review / testspec review 时使用。也适用于用户说「用例写完了帮我看看」「检查一下覆盖度」「用例有没有问题」的场景。支持默认模式和 --deep 深度模式。
---

# testspec-review：用例评审

## 核心约束

只给可执行、可定位、可修复的结论：每条问题必须指向具体 `case_id` 或 `TP_ID`，并给出明确整改动作。

## 职责

以独立评审视角，对测试用例做 14 维度交叉验证，输出结构化 `review-report.md`，并为上游 skill 提供可落地的反馈闭环。

## 当前变更目录

参见 `../testspec-shared/common.md` 中的「当前变更目录定位规则」。

## 共享规则源

- 评审模板：`review-report-template.md`
- 维度细则：`references/review-dimensions.md`
- 上下文协议：`../testspec-shared/context-protocol.md`

---

## 深度策略（统一语义）

默认执行 `auto` 模式：Agent 先判断复杂度和风险，再决定标准深度或加深深度。

- `auto`（默认）：按信号自动选择
- `--deep`（显式）：强制加深深度，不再降级

### auto 信号

**触发加深检查：**
- 用例总数 > 50
- 涉及模块数 > 5
- 用例类型 ≥ 3
- Strict 模式（`schema_version: 2` 且 `tp_refs` 完整）
- 上游 `material_quality = low`
- 上游 `risks_identified` 非空
- 上游 `open_questions` 非空

**可保持标准深度：**
- 用例总数 < 20
- 模块数 ≤ 2
- 上游 `material_quality = high`

### 深度行为差异

- 标准深度：执行 14 项检查，H3 对高风险 TP 全解释
- 加深深度：执行 14 项检查，额外读取 `requirements-analysis.md`，H3 对所有 TP 全解释，H5 最低覆盖类型要求提高到 3

评审开始时必须向用户说明当前深度及理由。

---

## 输入策略

### 必读文件

- `testcases.json`（变更目录根目录或 `artifacts/` 下）
- `specs/testpoints.md`

### 可选文件

- `requirements-analysis.md`（`--deep` 或 auto 加深时建议读取）

### 输入健康检查（失败即终止）

1. `testcases.json` 存在且可解析
2. 顶层包含 `testcases` 数组且非空
3. `specs/testpoints.md` 存在且包含 TP_ID

若失败：终止评审并提示先补齐上游产物（`testspec-generate` 或 `testspec-points`）。

### 模式判定

- **Strict**：`schema_version: 2` 且所有用例有非空 `tp_refs`
- **Legacy**：否则

Legacy 模式仍可评审，但 R6/H3 置信度下调，并在报告中明确升级建议。

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
3. **判定 Strict/Legacy 模式**
4. **判定深度（auto 或 --deep）并向用户说明**
5. **加载维度细则**：`references/review-dimensions.md`
6. **按 R1→R6 执行规则检查**
7. **按 H1→H8 执行启发式检查**
8. **生成报告**：按 `review-report-template.md` 填写全部结果
9. **计算总体置信度**
10. **输出总结与闭环建议**

---

## 报告要求

`review-report.md` 至少包含：

- 评审模式（Strict/Legacy）
- 深度（标准/加深）与触发原因
- 14 项检查矩阵
- S1/S2/S3 问题列表（每条带 ID、影响、建议）
- 总体结论（通过/有问题）
- 置信度（高/中/低）

---

## 反模式识别

| 反模式 | 表现 | 修正 |
|--------|------|------|
| 走形式检查 | 全部“通过”但无证据 | 每项至少给 1 个量化指标 |
| 模糊建议 | “建议优化”“需要改进” | 明确到字段和修改动作 |
| 遗漏 ID | 问题无 case_id/TP_ID | 所有问题绑定具体实体 |
| 比例至上 | 只看占比不看内容 | 先核实关键场景是否真实覆盖 |
| 忽视上游 | 不消费风险/待澄清信息 | 强制读取上游 context |
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

在 `review-report.md` 末尾按 `../testspec-shared/context-protocol.md` 写入：

```markdown
<!-- testspec-context
{
  "source_skill": "testspec-review",
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
✅ 评审完成 | 模式: <Strict/Legacy> | 深度: <标准/加深> | 置信度: <高/中/低>
📄 报告: testspec/changes/<name>/review-report.md
📊 总评: <S1> 个 S1 + <S2> 个 S2 + <S3> 个 S3
```

## 产物

- `testspec/changes/<name>/review-report.md`
