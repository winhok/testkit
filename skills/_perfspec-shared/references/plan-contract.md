# PerfSpec 需求与计划契约 v1

这是 agent 产物契约，不是现成的跨工具编译器。JSON 结构由宿主制作和复核。所有路径相对显式项目 root，秘密仅引用环境变量名。数字用明确单位，禁止 NaN/Infinity。

## requirements.json

必需：schema_version=1、spec_id、status=draft|ready、sources[{id,path,sha256,revision}]、scope、out_of_scope、goals、scenarios、decisions、blockers。
每条 goal/decision 有 id、value（未知用 null）、unit（如适用）、state=unknown|proposed|confirmed、basis。scenario 有稳定 id、requirement_refs、case_refs（local 可空）、旅程描述与业务 oracle。分析阶段允许未知值；ready 时目标/范围/负载单位/成功条件/SLA 的关键 blocker 必须清零。
无数值 SLA 的探索容量任务可 ready，但明确 discovery_only，结果不形成 SLA passed。

## plan.json

必需：schema_version=1、spec_id、status、sources（含 requirements 摘要）、target、runner、scenarios、profiles、data、monitoring、stop_conditions、comparison、blockers。

- target：id、platform=api|web、url、environment、build（执行前可 unknown，但正式 freeze 必须真实可核验）、identity_basis。
- runner：name=jmeter|locust|k6、version（未知明确标 unknown）、asset_path、capabilities[{feature,status,basis}]，status=supported|conditional|unsupported|unknown。
- scenarios：id、required、exclusion_reason（optional 必需）、requirement_refs、case_refs、steps、thresholds、sample_policy。每个 step 明确 id、method/path 或原生业务动作、label、输入/提取关联、assertions、effect 和 cleanup；不把依赖拆成无关并行接口。
- profiles：id、type、scenario_ids、load、phases、measurement、graceful_stop_seconds；共享业务逻辑，负载曲线独立。
- data：类别/分配/消耗模型、dataset_paths、seed_assets、cleanup_assets、隔离标记、secrets_env；非复用数据另给 required_entities 与 calculation（全部耗数阶段和余量依据）；生成数据与已实际准备的数据区分。
- monitoring：压测机资源采集、所需服务端信号、时间同步依据、必需/可选和采样周期。
- stop_conditions：指标/业务风险、阈值、连续窗口、动作；已授权负载上限和到期停止不隐式扩大。
- comparison：baseline_run（可 null）、controlled_dimensions、allowed_differences、regression_rules。

## 示例片段（完整计划仍需上述字段）

```json
{
  "load": {
    "model": "open",
    "unit": "iterations_per_second",
    "stages": [{"duration_seconds": 60, "target": 20}],
    "max_vus": 100,
    "think_time_seconds": 0
  },
  "measurement": {
    "phase": "steady",
    "duration_seconds": 60,
    "min_samples": 500,
    "load_tolerance_pct": 5,
    "max_dropped_iterations": 0
  },
  "thresholds": [
    {"id": "PERF-001", "metric": "request_duration_ms", "selector": "submit", "statistic": "p95", "operator": "<=", "value": 500, "unit": "ms", "basis": "confirmed requirement"},
    {"id": "PERF-002", "metric": "business_failure_rate_pct", "selector": "checkout", "statistic": "rate", "operator": "<=", "value": 1, "unit": "%", "basis": "confirmed requirement"}
  ]
}
```

closed 使用 unit=users；open 使用 iterations_per_second。请求 RPS 需业务迭代到请求的明确映射，不能假定 1:1。closed 的实际并发和必要吞吐分别记录。负载容差是已确认规则，不能测试后挑选。stages 目标非负，至少一段有正负载，duration>0；0 用户只用于 ramp/cooldown。
ready 计划必须有非空 profiles，覆盖所有 required 场景；每个 profile 的阶段和测量时长为正，测量引用已有 phase 且不超过其时长，phases 按顺序对应负载时间轴，总时长不得超过负载阶段总时长。测量 phase 必须包含正负载，不能仅测零负载冷却期。尚无可执行负载的计划保留 draft 与 blocker。
每个 metric 定义必须给出单位、采样范围、失败样本处理和测量方法；阈值操作符显式区分 < 与 <=。业务完成率与 HTTP 成功率分别定义。
每条阈值必需 id、metric、selector、statistic、operator、value、unit、basis，ID 在场景内唯一；ready 时文字字段非空、value 为有限数值，operator 使用 <、<=、>、>=、== 或 !=。draft 的未知定义可以显式 null 并列 blocker，但不能省略字段到 evaluate 阶段才发现。

## 审查清单

- id 唯一、场景/profile/步骤引用有效、依赖无环，required 场景不会消失。
- 所有脚本、数据和 runtime override 纳入有效输入；来源内容改变即重新审查。
- 阶段时间窗、负载单位和采样排除策略可执行，目标实际值能够被工具采集。
- 复杂协议/插件/调度需要验证依据。unknown 或 unsupported 的必需能力阻塞执行，不降级。
- 非复用数据按测量及其他耗数阶段的迭代率与时长估算；closed 无吞吐依据时标待 smoke 校准。cleanup 只覆盖本次可识别实体。
- 计划先定义正确性与 SLA，再设计执行；工具默认成功码、默认百分位或退出码不替代它们。

## 完整合成产物

[example-artifacts.md](example-artifacts.md) 路由仓库完整合成项目。目标环境、URL 和构建均为 fixture；哈希对应实际文件内容。requirements 和 plan 示例是 ready，脚本生成成功评测可直接复用其完整输入，缺少 endpoint/auth/数据定义的评测只能作为 blocker 场景。
