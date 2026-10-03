---
name: perfspec-plan
license: MIT
description: 制定工具无关的性能测试计划：业务场景、开放或封闭负载模型、测量窗口、SLA、数据策略、能力差异与执行退出条件。用户明确要压测方案或性能计划时使用，适配 JMeter、Locust、k6；不负责普通 TestSpec 策略、生成脚本或实际压测。
---

# PerfSpec：测试计划

将已确认性能目标转成可审查计划，统一测试意图，保留执行工具差异。

读取 [生命周期](../_perfspec-shared/references/lifecycle.md) 与 [计划契约](../_perfspec-shared/references/plan-contract.md)。按所选工具读取一份 [JMeter](../_perfspec-shared/references/jmeter.md)、[Locust](../_perfspec-shared/references/locust.md) 或 [k6](../_perfspec-shared/references/k6.md)，不加载无关适配器。

## 输入

优先读取 `requirements.json`、`analysis.md` 和已有 TestSpec strategy。允许用户提供完整性能需求直接进入本阶段，补齐来源映射即可，不强制重走 analysis。
未确认的目标、负载单位、业务成功条件和关键 SLA 是 blocker；草案可以落盘，但不能标 ready。

## 计划

1. 将业务逻辑与负载 profile 分开。同一场景可以复用到 smoke、average、stress、spike、soak、breakpoint；只规划与目标相关的类型，不强制生成六套。
2. 定义 closed（并发用户）或 open（迭代到达率）模型，明确数量单位。开放模型的 rate 是迭代数，不自动等于 HTTP 请求数。保留阶段曲线、think time/pacing、超时和优雅停止。
3. 分开 ramp、warmup、measurement 和 cooldown；写明哪些样本进入判定。不能用包含爬坡的总时长替代恒定负载持续时间。
4. 每场景定义请求/旅程 oracle、稳定标签、依赖、业务配比、判定阈值、最少样本或最短测量时间。缺少标准不能判 passed。
5. 选择现有原生脚本或待生成脚本，记录工具版本、协议和插件能力。标明 supported/conditional/unsupported/unknown 与依据。不支持的模型不得静默降级；自定义调度或插件需要单独证明。
6. 设计数据隔离、唯一性、消耗和清理。非复用数据按预计迭代数 × 每次消耗 × 说明了依据的余量计算；closed 模型无迭代速率依据时用 smoke 校准，不能直接以线程数倍数断言够用。
7. 定义目标构建与环境、压测机资源监控、目标负载容差、中止条件、负责人及恢复/清理动作。生产、外部服务和云费用按已有授权处理，计划不授予执行权限。
8. 基线比较预先列可比条件与回退标准；来源修订、业务定义、数据类别、负载、测量口径、环境或工具配置不同，列差异，不直接比较。

## 输出

写 `plan.json` 与 `plan.md`；字段和审查规则见计划契约。结构化文件是后续生成、执行和评估的共同输入。
ready 只表示计划关键决策已确定，不表示脚本已验证或环境已可执行。
执行前所需 capability 缺口可以先明确标记，不能从规划时的工具选择推断已可访问目标。
下一阶段为 `perfspec-generate`；已有经验证原生资产可交给 `perfspec-run`。
