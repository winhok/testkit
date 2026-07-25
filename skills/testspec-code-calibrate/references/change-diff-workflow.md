# Change-Diff 校准工作流

仅在 `mode=change-diff` 时使用本 reference。

## 内容

- 快照选择
- 安全收集
- 候选检索
- 语义追踪
- 分类映射
- 报告与新鲜度

## 快照选择

必须明确：

- 仓库访问权限和仓库相对范围
- 非敏感仓库标签
- 本地 Git 执行所需的真实 base/head ref
- artifact 中保存的安全 base/head 标签，例如 `production`、`test` 或 `requirement`
- 比较模式

按问题选择：

| 问题 | 比较方式 |
|---|---|
| test 相比 production 累积了哪些变化？ | `production...test` |
| requirement 分支从分叉点起新增了什么？ | `production...requirement` |
| requirement 还有什么需要合并到 test？ | `test...requirement` |
| 本地 staged 了什么？ | staged |
| 授权 worktree 相比 base 新增了什么？ | worktree |

表示分支意图时默认使用 three-dot。只有用户明确要求 tip-to-tip 比较时才使用 two-dot，绝不能在两者间静默降级。校准过程中不得运行 `git fetch`、checkout、merge、rebase、pull 或 push。

## 安全收集

写入 `<change>/artifacts/change-snapshot.json`：

```bash
python "<skill-dir>/scripts/collect_change_snapshot.py" \
  --repo-root "<authorized-local-repo>" \
  --repository-label "<safe-label>" \
  --base-ref "<actual-local-ref>" \
  --head-ref "<actual-local-ref>" \
  --base-label "<safe-role-label>" \
  --head-label "<safe-role-label>" \
  --scope "<repository-relative-scope>" \
  --output "<change>/artifacts/change-snapshot.json"

python "<skill-dir>/scripts/validate_change_snapshot.py" \
  --input "<change>/artifacts/change-snapshot.json"
```

收集器只持久化 commit identity、merge-base、时间戳、dirty state、文件统计、相对路径、数字 hunk 范围和临时 Diff 的 SHA-256；绝不保存真实 ref、仓库根目录、remote、原始 Diff、变更行或代码片段。

除非用户明确授权替换，否则不得覆盖已有快照。HEAD、index、worktree 状态、范围或 canonical revision 变化时必须使用新快照。

## 候选检索

从当前 canonical `REQ-*` / `AC-*` 建立候选关联；若有当前 testspec-native 测试点或用例，也可使用。历史导入用例只能作为次级搜索提示。

候选提示可使用：

- 字段和可见标签 token
- 路由或命令概念
- 状态与动作词汇
- 安全相对路径邻近关系
- 变更的数字 hunk 范围

记录 `candidate_strategy=keyword-hints-only`。token 命中不能证明一致、冲突、已实现、优先级或测试成功。创建 finding 前，必须读取对应的临时 hunk 和相连运行时路径。

## 语义追踪

为每项 change-diff finding 分配一个 `change_trace_status`：

| 状态 | 含义 |
|---|---|
| `matched` | 变更证据支持 canonical 行为或可观察的 code-only 行为 |
| `partial` | 存在相关变化，但可观察路径不完整 |
| `not-observed` | 本 Diff 未观察到 canonical 行为，不代表全局不存在 |
| `deviation` | 变更证据与 canonical intent 冲突 |
| `unknown` | 范围、解析、配置或矛盾证据使结论无法确定 |

每项 `matched` 或 `deviation` finding 至少包含一个 `source=diff` 的 evidence item。未变化的支持代码使用 `source=snapshot`。evidence layer 标记为 `entry`、`enforcement`、`state`、`feedback` 或 `external`。

无法映射的变更路径记录在 `change_trace.unmapped_changes`；它只是评审关注清单，不能证明需求缺失。

## 分类映射

将 trace status 映射到现有 calibration contract：

| Trace status | 允许的 classification |
|---|---|
| `matched` | `aligned` 或 `code-only` |
| `deviation` | `conflict` |
| `partial` | `unknown` |
| `not-observed` | `unknown` |
| `unknown` | `unknown` |

不得因 Diff 缺失而产生 `prd-only`。`prd-only` 需要 comparison 模式对相关实现做范围明确的搜索，不能只依赖缺少变更 hunk。

`partial` 和 `not-observed` 使用 medium/low confidence。应用既有 `end-to-end/enforcement-layer/partial` 证据门槛。`end-to-end` change finding 至少提供两个不同的 evidence layer。

## 报告与新鲜度

校验 JSON 并渲染不含代码片段的报告：

```bash
python "<skill-dir>/scripts/validate_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --canonical "<change>/requirements.md" \
  --snapshot "<change>/artifacts/change-snapshot.json"

python "<skill-dir>/scripts/render_code_calibration.py" \
  --input "<change>/artifacts/code-calibration.json" \
  --output "<change>/artifacts/code-calibration.md"
```

对话中只报告使用安全产品语言的 finding 摘要、数量、安全标签、warning、未决 `Q-*` 和 artifact 路径。不得粘贴原始代码、Diff 内容、私有 ref 或代码片段。摘要必须保留 `not-observed` 和 `unknown` 限定词，不能改写成“缺少实现”。
