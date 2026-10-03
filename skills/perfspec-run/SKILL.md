---
name: perfspec-run
license: MIT
description: 运行已确认范围内的性能测试，使用 JMeter、Locust 或 k6 原生资产完成执行前就绪检查、小负载验证、正式负载、资源监控、中止恢复、清理与证据记录。用户明确要求压测执行时使用；只写计划、生成脚本或分析已有结果不触发实际请求。
---

# PerfSpec：测试执行

运行已授权、可证明目标身份的性能场景；记录真实执行，失败和中断也保留。

读取 [执行与验收交接](../_perfspec-shared/references/execution.md) 和现有 [执行契约](../_test-run-shared/references/execution-contract.md)。按工具只读 [JMeter](../_perfspec-shared/references/jmeter.md)、[Locust](../_perfspec-shared/references/locust.md) 或 [k6](../_perfspec-shared/references/k6.md)。

## 执行准备

1. 核对 plan、asset manifest、原生脚本及数据内容。确认实际 target URL、部署 build、环境与角色；未知 build 可做明确限定的 local 观察，不能伪造正式验收身份。
2. 将工具可用性与操作授权分别检查。已有授权覆盖本次目标、负载、时长和副作用时继续；超出范围、费用或新目标需明确授权。GET 压测也会产生负载，不能把 read 权限解释为任意压力许可。
3. 检查脚本、依赖、鉴权、worker、采样、压测机资源和监控。数据缺失时先区分“有已授权 seed 方案待执行”与“数据来源/授权缺失”；后者 blocked，不安装或下载未授权依赖。
4. 按需准备数据：核对 seed 资产、数量/速率及写入与清理授权，将准备动作和输入先冻结到独立 local 运行；执行 seed，逐步登记本次实体和失败副作用。部分失败先按记录恢复或清理，不盲目重放。校验数据数量、分片、业务可用性和清理能力，保存 preparation.json；只有数据就绪才进入 smoke。

## 运行

5. 在独立 smoke 运行中先冻结当前输入与必测 checks，再执行小负载功能验证，核对业务成功、动态关联和清理。可复用对当前输入、目标与授权仍有效的已有 smoke 证据。若 smoke 消耗正式数据，按授权补充并重新校验；输入改变需重新审查，不覆盖旧证据。
6. 数据和 smoke 验证完成后，在新的 `test-runs/<run-id>/` 中冻结正式 profile 的全部必测 checks（含 blocked 项）及最终计划、脚本、数据/生成定义和有效参数，再执行正式负载。正式 acceptance 还需当前 TestSpec requirements/cases/strategy 和全部用例范围。采集真实起止时间、工具/worker 版本、目标身份、输入前后摘要、原始结果和日志。
7. 按计划监控压测机和已授权后端信号；记录实际用户/到达率、completed/interrupted/dropped、业务完成率和阶段。资源饱和是测量有效性疑点，不凭 CPU 单一阈值确定后端根因。
8. 达到中止条件时按原生工具优雅停止，记录触发信号和未完成旅程。中断恢复先核对已写入实体、会话和清理状态，不自动重放写操作。新尝试保留旧失败。
9. 仅清理本次可识别数据、会话、进程及监控。cleanup required 的失败或 unknown 阻止通过；工具退出 0 不证明 SLA 或清理完成。

## 交付

保存 `execution.json`、原始结果、资源监控和脱敏日志，字段见执行参考。收集失败、blocked、aborted 也有记录，不生成伪 JTL 或假测量值。
将实际状态交给 `perfspec-evaluate`。通过受控 observation 关联当前契约，不注册不存在的 jmeter/locust/k6 原生 binding，不从模板直接生成 passed。
