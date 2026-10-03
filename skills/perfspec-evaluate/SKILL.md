---
name: perfspec-evaluate
license: MIT
description: 评估已有 JMeter、Locust、k6 性能执行证据，分别判断测量有效性、负载达成、功能与 SLA，并在条件可比时检查基线回退、按需关联监控日志定位瓶颈。用户要性能报告分析或容量结论时使用；本阶段只读已有证据，不重新压测、降低阈值或自动修改计划。
---

# PerfSpec：结果评估

将真实原生结果转成有范围、有依据的性能结论，不重新执行测试。

读取 [结果与比较契约](../_perfspec-shared/references/result-contract.md)。验收交接时读取 [执行参考](../_perfspec-shared/references/execution.md) 与 [共享执行契约](../_test-run-shared/references/execution-contract.md)。解释原生字段时按需读取 [JMeter](../_perfspec-shared/references/jmeter.md)、[Locust](../_perfspec-shared/references/locust.md) 或 [k6](../_perfspec-shared/references/k6.md)。

## 输入

读取执行前冻结的计划与输入快照，以及执行后采集的原生结果、execution.json、当前目标身份和可选基线/监控。原生结果与执行记录不得提前生成或作为执行前来源冻结。
只有历史报告时可做 report-only，保留原始结论和来源限制；不补造执行前 freeze、时间或部署身份。

## 评估

1. 验证原始证据、输入摘要、目标、配置和实际时间窗口。当前目标或源内容不同则对当前验收 stale；历史测量事实保留。
2. 按冻结场景全集映射稳定标签，显式列漏测、未映射标签和中断；不从成功结果反推测试范围，不把 transaction 父样本与请求子样本重复统计。
3. 分别计算 execution_validity、load_status、functional_status、sla_status 与 verdict，规则见结果契约。工具退出码、业务成功率和性能 SLA 各自保存。
4. 对预热/爬坡/正式测量分窗，使用原生字段定义和计算依据。HTTP 请求耗时、连接耗时、TTFB、业务旅程时间不能互相替代。没有阶段信息的全程 summary 不冒充稳态结果。
5. 对缺失数据保持 null/unknown；声明来源、样本数和分位数算法。worker 或标签 P95 不能求平均得到整体 P95；有兼容原始样本/直方图才重新聚合，否则分别展示。
6. 基线比较先检查场景、profile、数据类别、工具配置、环境与指标口径。构建变化可作为待测变量；其余差异需控制或证明可比。阈值事后修改不能洗绿原运行；计划修订产生新运行。
7. 诊断按需关联已提供或已授权查询的 CPU/GC/连接池/数据库/网关/trace。对齐时区和时钟偏差，区分压测机与服务端。明确事实、假设、置信度和可证伪动作；相关性不自动等于根因。

## 输出与交接

写新的 `performance-result.json` 与 `performance-report.md`，保留原始结果；字段见结果契约。报告范围、负载目标/实际值、四项状态、阈值/失败、基线差异、诊断依据、清理、限制和下一步。
需要 TestKit 验收时，按执行参考生成可审查 observation 并关联原始证据；由 `test-acceptance` 计算冻结范围结论。
SLA 达标、局部性能检查通过、版本验收通过和生产发布是不同结论。工具/环境能力缺口不能靠报告措辞补齐。
