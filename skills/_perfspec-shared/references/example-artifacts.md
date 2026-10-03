# 完整合成产物与历史报告

仓库的 [synthetic-perfspec](../../../examples/synthetic-perfspec/) 是完整合成项目，项目 root 为该目录：

- [来源](../../../examples/synthetic-perfspec/source.md)、[需求](../../../examples/synthetic-perfspec/perfspec/catalog/requirements.json)、[分析](../../../examples/synthetic-perfspec/perfspec/catalog/analysis.md)。
- [计划 JSON](../../../examples/synthetic-perfspec/perfspec/catalog/plan.json)、[可读计划](../../../examples/synthetic-perfspec/perfspec/catalog/plan.md)、[资产 manifest](../../../examples/synthetic-perfspec/perfspec/catalog/asset-manifest.json)。
- [k6 原生资产](../../../examples/synthetic-perfspec/perfspec/catalog/assets/k6/catalog.js)、[可适配的 Locust 资产](../../../examples/synthetic-perfspec/perfspec/catalog/assets/locust/catalog.py)。
- [合成冻结 scope](../../../examples/synthetic-perfspec/test-runs/catalog-load/scope.json)、[执行记录](../../../examples/synthetic-perfspec/test-runs/catalog-load/execution.json)、[原始合成观察](../../../examples/synthetic-perfspec/test-runs/catalog-load/raw/observation.json)、[完整结果](../../../examples/synthetic-perfspec/test-runs/catalog-load/performance-result.json)、[报告](../../../examples/synthetic-perfspec/test-runs/catalog-load/performance-report.md)。
- [无计划的历史结果](../../../examples/synthetic-perfspec/history/performance-result.json)：plan_sha256、target、execution 等缺失项是 null，checks 为空，保留 summary 摘要与限制，verdict=inconclusive。

fixture 的 execution/metrics 是标明 origin=synthetic、tool_executed=false 的协议示例，不是 k6/Locust 实测，不得移入真实 acceptance。静态版本时间也不得用于真实 record；单元测试在临时目录冻结后用当前测试时间登记合成 observation，只验证本地记录契约。

按阶段仅读取需要的输入：generate 使用完整 ready plan 和对应原生资产，evaluate 使用计划、冻结 scope、执行记录与原始观察，不能把参考 performance-result 当作模型输入答案。路径/摘要以示例 root 为准，复制到其他 root 后重新核对。

评测时由 grader 调用 [eval_artifacts.py](../scripts/eval_artifacts.py) 校验实际文件和绑定；模型不加载此检查器。维护者可运行 `python skills/_perfspec-shared/scripts/test_eval_artifacts.py` 验证合成产物与记录闭环，检查器不执行原生工具或认证 SLA。
