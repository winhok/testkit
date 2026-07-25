# 可观察实现草稿——不是 canonical 文档

> 本文只记录从明确授权代码中观察到的行为。它不是产品批准的 PRD，不能定义 test oracle，必须通过 `testspec-update` 获得确认。

## 快照

| 字段 | 值 |
|---|---|
| 仓库标签 | `<non-sensitive-label>` |
| Ref / commit | `<ref>` / `<commit>` |
| 授权范围 | `<repository-relative paths>` |
| 证据角色 | `<reference/verification-baseline/change-evidence>` |

## 可观察模块边界

描述可达的用户入口和排除范围。不得推断代码中不可见的产品目的。

## 可观察行为

使用 draft ID，绝不能使用 `REQ-*` 或 `AC-*`。

| Draft ID | Calibration finding | 可观察行为 | 证据 | 覆盖 | 置信度 | 产品问题 |
|---|---|---|---|---|---|---|
| OBS-001 | CAL-001 | `<observable behavior>` | `<relative path:symbol:lines>` | `<end-to-end/enforcement-layer/partial>` | high/medium/low | Q-001 |

## 可观察角色与权限

| 参与者 | 强制执行的行为 | 证据 | 置信度 |
|---|---|---|---|
| `<actor>` | `<observable permission>` | `<relative evidence>` | `<level>` |

## 可观察字段、状态与错误

只记录授权范围内可见的行为。标记 feature flag、环境条件、partial layer 和不确定映射。

## 必需的产品确认

针对每个 `OBS-*`，确认该行为属于：

- 预期行为，应成为需求
- 实现缺陷
- 仅历史兼容
- 已废弃或超出范围

使用稳定 `Q-*`。获得答复后，运行 `testspec-update` 创建或修改 canonical `requirements.md`；不得直接把此 draft 编辑成 canonical 文档。
