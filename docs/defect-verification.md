# 验证缺陷修复

`defect-verification` 组织缺陷重现、修复版本定向复测和关联回归，用相互独立的 RED、GREEN、REGRESSION 证据判断缺陷能否关闭。

## 开始前需要什么

- 缺陷 ID 或可稳定识别的问题描述。
- 原始预期和目标失败特征。
- 关键初始条件、账号、数据和环境。
- 旧版与修复版的构建标识。
- 需要覆盖的关联回归范围。

局部 Bug 可以直接开始，不要求先建立完整 TestSpec；正式回归应使用已经评审的范围。

## 三阶段证据

| 阶段 | 要证明什么 |
|---|---|
| RED | 旧版在目标条件下真实出现原失败特征 |
| GREEN | 修复版在相同关键条件和 oracle 下通过原断言 |
| REGRESSION | 相关路径、边界、角色和历史风险没有新增失败 |

安装、DNS、账号或环境故障属于阻塞，不是 RED 成功。缺少旧版时可以继续检查修复版，但必须保留 `missing baseline`，不能给出完整 verified 结论。

## 执行与结果

每个阶段单独冻结目标和范围，实际操作由当前可用的 [`app-test`](app-test.md) 或 [API 自动化测试](api-test-automation.md) 完成。验证器核对各阶段证据引用，生成 `defect-result.json`，最终状态为 `verified`、`incomplete` 或 `failed`，并列出未复现、未验证和不可比较的部分。

典型请求：

```text
在旧 APK 复现这个登录失败，再在修复版做同条件复测和关联回归
验证接口缺陷 #123 是否修复，保留 RED/GREEN/REGRESSION 证据
```

缺陷复测不会自动扩展成修改业务代码；根因分析也不能替代修复证据。完整执行契约见 [`defect-verification`](../skills/defect-verification/SKILL.md)。
