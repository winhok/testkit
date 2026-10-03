# PerfSpec 性能测试工作流

PerfSpec 将业务性能目标连接到原生压测资产、真实执行和 TestKit 证据验收。五个入口可独立使用，已有脚本或结果无需重走全部阶段。

| 阶段 | Skill | 主要产物 |
|---|---|---|
| 需求分析 | [perfspec-analysis](../skills/perfspec-analysis/SKILL.md) | analysis.md、requirements.json |
| 测试计划 | [perfspec-plan](../skills/perfspec-plan/SKILL.md) | plan.json、plan.md |
| 测试资产 | [perfspec-generate](../skills/perfspec-generate/SKILL.md) | 原生脚本、数据/清理资产、asset-manifest.json |
| 测试执行 | [perfspec-run](../skills/perfspec-run/SKILL.md) | execution.json、原始结果、资源与清理证据 |
| 结果评估 | [perfspec-evaluate](../skills/perfspec-evaluate/SKILL.md) | performance-result.json、performance-report.md |

```text
TestSpec / 已确认业务性能需求 / 已复核 API 契约
  → analysis → plan → generate → run → evaluate
                                        ↓
                                 test-acceptance
```

数据策略在 plan 中定义，造数资产在 generate 中制作，实际造数/清理在授权的 run 中完成；准备动作先独立冻结并登记本次实体，部分失败保留副作用，smoke 后校验最终数据再冻结正式 profile。监控日志诊断是 evaluate 的可选分支。

## 多工具支持的含义

当前提供 JMeter、Locust、k6 的原生资产制作、执行和分析指导，由宿主 agent 使用已安装且已授权的工具完成；不捆绑压测工具、依赖安装器、云服务或自动跨工具编译器。原生文件和命令需要在实际工具版本下验证。工具能力声明和技能文档不等于已完成真实运行验证。

| 工具 | 原生资产 | 负载语义与限制 |
|---|---|---|
| JMeter | JMX | 标准线程组为并发模型；精确开放到达率需验证对应线程组或插件 |
| Locust | Python locustfile | 用户/task 循环为并发模型；spawn-rate、pacing、用户曲线不自动保证全局开放到达率 |
| k6 | JavaScript / 版本支持的 TypeScript | 原生 VU 与 arrival-rate executors；到达率按迭代计，需要检查 dropped iterations |

统一业务目标、单位、负载意图、测量窗口、SLA 和证据，不掩盖工具功能差异。每次计划只声明实际所用适配器；未支持特性明确阻塞或报告限制。

## 使用示例

```text
分析结算链路的性能需求，复用当前 TestSpec 的范围和 SLO，列出信息缺口。
设计 20 次业务迭代/秒的性能计划，说明 k6 与 Locust 的调度差异。
按已确认计划适配现有 locustfile，只生成资产，不执行请求。
在已授权测试环境运行这个 JMX，先验证小负载，保留压测机监控与清理证据。
分析这次 k6 结果，分别判断负载是否达到、业务是否正确、SLA 是否满足。
```

## 目录和边界

规范放在目标项目的 `perfspec/<spec-id>/`；实际执行在新的 `test-runs/<run-id>/` 中保存独立 profile、尝试和证据。不要覆盖原始结果或混合 smoke/正式样本。
默认本地业务材料放入上述工作区，不提交真实凭据、业务数据和 HAR/响应正文。公开 fixture 使用合成数据。

现有 `generate-api-artifacts` 继续只负责 OpenAPI 工具导出，不执行压测。PerfSpec 的结果不会改变 TestSpec context、用例或 API result schema。
当前执行契约没有性能工具原生 binding，验收通过可审查 observation 与原始证据衔接。记录工具不自动验证性能计算和外部事实；来源、目标、采样和清理缺口仍会影响结论。完整交接见 [执行参考](../skills/_perfspec-shared/references/execution.md)。
无当前 TestSpec 输入可做局部性能检查；正式版本验收需要当前 requirements/cases/strategy 与冻结的完整确认范围。性能达标不代表全量验收或发布。

## 验证与来源

新增合成行为 eval 覆盖阶段边界、负载语义、证据不足、清理、中止和基线差异；仓库验证检查 fixture 与断言，不代表模型行为评测已通过。未执行设备、外部 API、真实压测或云测试。
设计依据与官方链接集中在 [生命周期参考](../skills/_perfspec-shared/references/lifecycle.md) 和三个工具参考，契约是 TestKit 本地设计。新增内容独立编写，没有引用临时导入目录。

完整合成产物与 report-only 示例见 [示例路由](../skills/_perfspec-shared/references/example-artifacts.md)。合成值明确标识，没有实际工具执行；正式产物断言和本地记录闭环回归已纳入检查。
