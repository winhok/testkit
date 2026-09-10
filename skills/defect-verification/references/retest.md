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

## 来源失败与再验收（可选扩展）

schema_version 保持 1；独立缺陷没有来源运行时省略 lineage。若由已有执行/验收失败发起，必须添加 lineage.source；尚无再验收时省略 reacceptance，不填虚构运行。所有目录相对 --root，scope_sha256 为已冻结 scope.json 的原字节摘要。

```json
{
  "lineage": {
    "source": {"run_dir": "test-runs/initial", "run_id": "initial", "scope_sha256": "<sha256>", "check_ids": ["CHK-LOGIN-004"]},
    "reacceptance": {"run_dir": "test-runs/reaccept", "run_id": "reaccept", "scope_sha256": "<sha256>"}
  }
}
```

source.check_ids 必须非空、无重复，且在来源运行与 RED 中确实失败。源运行可包含其他缺陷；本 defect 只认领所列检查。来源、RED/GREEN、再验收使用相同 check ID、case ID、目标 ID、oracle、binding、effect 和 cleanup；RED/GREEN 及再验收中所列检查必须 required。来源目标匹配 RED，再验收目标匹配 GREEN。不同 ID/断言的历史运行不能强行关联，应按可比定义重新验证并说明缺口。

再验收必须是独立的新 mode=acceptance 运行，不能复用来源或任一复测阶段；冻结时间晚于这些运行的已登记尝试。重新确认正式范围与退出条件，保留其他未解决的必测项，不能只收集已修好的检查。

校验器要求来源全部 required check 在再验收中仍为 required 且检查身份不变；允许新增检查，不允许通过删项或降为 optional 洗绿。若产品改变了验收范围或 oracle，应另建经确认的新范围并说明不可直接关闭旧检查，不能强行套用这条可比关联。API 检查还比较所绑定 runner-definition 的摘要。

```sh
python <skills>/defect-verification/scripts/verify_defect.py --root <project> --input <defect.json> --current-targets <fresh-targets.json> --output <new-defect-result.json>
```

工具重新 evaluate 来源与再验收的 scope/attempt/evidence，并输出来源 attempts_sha256 和完整再验收结果；不信任手写 verified/passed。current-targets 为独立核实的当前 targets 数组，不能直接复制旧 scope 冒充当前身份。无再验收引用时不要求此参数。

输出顶层 status 仍为缺陷三阶段状态；lineage.reacceptance_status 为 not-run/passed/failed/blocked/inconclusive/stale。只有缺陷 verified 且整个新验收范围 passed 时才填 closed_check_ids。其他 Bug 导致新验收失败时，当前缺陷仍可 verified，但不声称整体缺口关闭。CLI 退出码 0 表示缺陷 verified 且已提供的再验收通过（未提供时只代表复测）；1 表示未通过/未完成，2 表示结构或关联无效。缺少任一复测阶段时返回 incomplete，不核验 lineage，也不宣称关联或再验收通过。
