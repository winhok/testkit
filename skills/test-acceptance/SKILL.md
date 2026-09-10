---
name: test-acceptance
license: MIT
description: 根据已确认的版本、冻结测试范围、执行结果和证据覆盖形成可复核的验收结论，识别漏测、阻塞、证据过期与未满足的退出条件。用户要验收版本、检查测试证据或汇总验收报告时使用；只整理已有报告不执行测试，用例入库仍走 testspec-publish。
---

# 测试验收

铁律：从冻结的全部必测项计算结论，不能用缺陷 verified 替代再验收。

读取 [共享执行契约](../_test-run-shared/references/execution-contract.md)。

## 按意图工作

- 计划正式验收：读取当前 TestSpec requirements、strategy、cases 和 review，通过现有版本与评审门禁，确认版本、环境、必测范围与退出规则，再 freeze。范围包含 blocked 项；执行由相应能力完成。
- 检查已有执行：验证 scope、全部 attempts、原始证据与当前目标版本，调用 evaluate。
- 只整理报告：读取已有结论与证据，保留状态，不发起执行、不改变冻结范围、不改判。
- 旧报告迁移：运行 migrate --check，再输出新文件；历史结果不自动成为当前验收。

## 判定与报告

使用 test_run.py evaluate --current-targets ...。工具计算 required checks 的覆盖和结论；输出记录合法性、执行状态、覆盖状态、acceptance_status、所有检查结果及未测原因。不得用总通过率掩盖关键用例遗漏，不手写 passed 绕过校验。

local scope 只能说明该局部检查，不能称版本全量通过。正式验收报告列出需求/用例版本、被测构建与环境组合、范围来源、通过/失败/漏测/阻塞/跳过、清理和重试、证据限制。已知必需断言证据不足时给 inconclusive。

源版本/内容或被测对象变化，保留历史事实并标注对当前目标 stale；重新冻结并执行受影响范围才能形成新的结论。正式验收不表示生产已发布，testspec-publish 不表示测试通过。

## 缺陷关联与再验收

由失败转入复测或核对已修复缺口时，按需读取 [复测关联契约](../defect-verification/references/retest.md)。将来源 run_id、scope 摘要及失败 check_ids 记录到 defect.json.lineage.source；不修改旧 scope 或 attempt。

再验收先确认全部必测范围（含其他未解决项），建立新的 acceptance run。执行和 evaluate 完成后将其引用写入新的 defect 输入记录，以 fresh current-targets 调用 verify_defect.py 核验关联。报告逐缺陷列出 defect_id、来源检查、复测状态、再验收运行和状态；仅引用工具计算的 closed_check_ids。只整理报告时使用已有结果，保留缺失或未核验关联，不触发复测或补造通过。
