# 复测契约

创建 defect.json，包含 schema_version=1、defect_id、expected、failure_signature、conditions，以及 phases.red/green/regression（各为相对于 --root 的 run directory）。
RED/GREEN 的检查应使用相同 oracle、case_id 和运行定义内容；被测 build 必须不同，环境/角色/初始条件保持可比较。如果必要测试定义变更，先对原版使用新定义重新 RED，不悄悄放宽预期。

逐检查比较稳定 ID、target_id、oracle、binding、required、effect 和 cleanup；全局 targets 列表相同不能替代检查目标一致。每个必测目标的 build 都应变化，不能只升级无关组件。三个阶段使用独立运行记录。有证据的 GREEN/REGRESSION 失败输出 failed；缺阶段、证据不足为 incomplete；结构或可比性违规为 invalid。

运行：
```sh
python <skills>/defect-verification/scripts/verify_defect.py --root <project> --input <defect.json> --output <new-defect-result.json>
```
工具重新读取各 run 的 scope/attempt/evidence 计算，而不是信任一个手写 phase=passed。RED 的 observation 需包含 defect_signature 与 failure_signature 完全一致；API 失败若无目标缺陷观察不可作为充分 RED。GREEN/REGRESSION 必需检查通过，任何 missing、stale evidence、混合重试或 cleanup 不明均不能 verified。

scope.sources 中需保存同一个 conditions 文件（kind=dataset），内容记录角色、fixture、复现动作与配置；三个阶段都引用相同摘要。不同阶段的目标构建不同，但平台、环境和目标 ID 一致。如果回归新增另一个组件，在独立 run 中报告，当前核验器只核验相同目标矩阵。

此工具验证记录的一致性，不认证缺陷本身、包来源或实际设备操作。输出必须与原始报告一起审查。
