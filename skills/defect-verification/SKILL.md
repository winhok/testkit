---
name: defect-verification
license: MIT
description: 组织缺陷重现、修复版本定向复测与关联回归，建立 RED、GREEN、REGRESSION 证据。用户要复现 Bug、验证修复、复测旧 APK 与新 APK 或判断缺陷是否关闭时使用；实际操作委托当前可用的 app-test/API 能力，不默认修改业务代码。
---

# 缺陷验证

读取 [retest.md](references/retest.md) 与 [共享执行契约](../_test-run-shared/references/execution-contract.md)。局部 Bug 可直接开始，无需完整 TestSpec；正式回归使用已评审的范围。

1. 明确 defect ID、原始预期、目标失败特征、关键初始条件、旧版/修复版身份及回归范围。
2. 每阶段建立独立冻结 scope，使用 app-test 或 api-test-automation 执行并登记所有尝试。
3. RED 必须证实目标失败特征；配置、DNS、安装、账号故障是阻塞，不是成功复现。
4. GREEN 在相同关键条件下通过原断言；条件或 oracle 改变须说明并重新确认可比性。
5. REGRESSION 覆盖相关路径、边界、角色和历史风险，按选择依据冻结范围。
6. 用 scripts/verify_defect.py 核验各阶段证据引用，输出 defect-result.json；报告 verified/incomplete/failed，以及未复现或未验证的部分。

缺失旧版可继续修复版检查，保留 missing baseline，最终不得标完整 verified。版本可用包摘要、构建号或可核实部署标识，不强制 Git。根因分析可调用诊断能力，但不是复测通过的替代证据。
