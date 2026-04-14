# 测试用例评审报告

**评审时间**: <timestamp>
**评审模式**: <mode> (Strict/Legacy)
**变更目录**: <change_dir>

---

## 总评

**结论**: <overall_conclusion>

**置信度**: <confidence_level>

### 结论总览矩阵

| 检查项 | 结果 | 关键指标 | 问题数 |
|--------|------|----------|--------|
| R1 覆盖度 | <result> | <metric> | <count> |
| R2 命名契约 | <result> | <metric> | <count> |
| R3 优先级分布 | <result> | <metric> | <count> |
| R4 字段完整性 | <result> | <metric> | <count> |
| R5 可执行性 | <result> | <metric> | <count> |
| R6 可追溯性 | <result> | <metric> | <count> |
| H1 冗余检测 | <result> | <metric> | <count> |
| H2 预期结果质量 | <result> | <metric> | <count> |
| H3 意图一致性 | <result> | <metric> | <count> |
| H4 前置条件充分性 | <result> | <metric> | <count> |
| H5 风险与边界覆盖 | <result> | <metric> | <count> |
| H6 可维护性建议 | <result> | <metric> | <count> |
| H7 回归价值评估 | <result> | <metric> | <count> |
| H8 测试价值与亮点 | — | 标杆用例数 | <count> |

---

## 规则检查

### R1: 测试点覆盖度

**结果**: <pass/fail>
**覆盖率**: <percentage>%

<问题列表>
- [S1/S2/S3] <问题描述>
  - **影响**: <影响说明>
  - **建议**: <整改建议>

### R2: 命名契约

**结果**: <pass/fail>
**违规数**: <count>

<问题列表>

### R3: 优先级分布

**结果**: <pass/fail>
**分布情况**: 冒烟 <count>%, P1 <count>%, P2 <count>%, P3 <count>%

<问题列表>

### R4: 字段完整性

**结果**: <pass/fail>
**缺失字段数**: <count>

<问题列表>

### R5: 可执行性最小条件

**结果**: <pass/fail>
**不满足条件数**: <count>

<问题列表>

### R6: 可追溯性

**结果**: <pass/fail>
**追溯完整性**: <percentage>%
**模式**: <Strict/Legacy>

<问题列表>

---

## 启发式检查

### H1: 冗余检测

**结果**: <pass/fail>
**疑似冗余对数**: <count>

<问题列表>

### H2: 预期结果质量

**结果**: <pass/fail>
**模糊表述数**: <count>

<问题列表>

### H3: 意图一致性

**结果**: <pass/fail>

#### 意图一致性评估表

| TP_ID | 用例数 | Action Match | Oracle Match | Scope Match | 结论 | 证据/说明 |
|-------|--------|--------------|--------------|-------------|------|-----------|
| <tp_id> | <count> | <score> | <score> | <score> | <conclusion> | <evidence> |

<问题列表>

### H4: 前置条件充分性

**结果**: <pass/fail>
**抽样数**: <count>
**不充分数**: <count>

<问题列表>

### H5: 风险与边界覆盖

**结果**: <pass/fail>
**覆盖类型**: <types>

<问题列表>

### H6: 可维护性建议

**结果**: <pass/fail>
**建议数**: <count>

<问题列表>

### H7: 回归价值评估

**结果**: <pass/fail>
**抽样数**: <count>
**仪式感用例数**: <count>

<问题列表>

### H8: 测试价值与亮点识别

**标杆用例数**: <count>
**可复用模式数**: <count>
**测试策略健康度**: <评语>

<亮点列表>

---

## 整改建议清单

### S1 阻断级（必须修复）

- [ ] <问题描述> - <建议>

### S2 重要级（应当修复）

- [ ] <问题描述> - <建议>

### S3 建议级（可选优化）

- [ ] <问题描述> - <建议>

---

**评审完成时间**: <timestamp>
