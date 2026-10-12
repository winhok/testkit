# Showcase: coupon discount / 优惠券测试设计

English | [简体中文](#简体中文)

A small, manually authored teaching example of requirements becoming test cases.
The files here are previews, not a validated TestSpec change, agent-run output,
or proof that a product passed testing. No target service or device is used.

## Try it

Install the full TestKit plugin, then open a writable project in your agent.
Copy the requirement below, or attach [requirements.md](requirements.md), and ask:

```text
Use TestKit to create a coupon-discount change from this requirement.
Analyze it, clarify missing rules, create test points, generate cases, and
review them. Export Excel if the Python dependencies are available.
Do not execute tests. Keep stage prerequisites and review findings visible.
```

Your agent needs model access. Excel export also needs the repository's Python
dependencies; see the [installation guide](../../docs/installation.en.md).
No extra API account, browser service, or device is needed for this design task.

## Input → test points → cases

- **Input:** [three requirement rules](requirements.md).
- **Test points:** eligibility boundary, exact discount, expired coupon, used coupon.
- **Preview:** [five test cases](cases.md), each linked to a requirement and a test point.
- **Expected workflow artifacts:** proposal, requirements, analysis, test points,
  JSON cases, optional Excel, and review under `testspec/changes/coupon-discount/`.
  The agent creates the required context metadata; these preview files do not replace it.

Example: R1 → TP-01 (eligibility boundary) → TC-01/02/03.
A subtotal of CNY 99.99 is rejected; CNY 100.00 becomes CNY 80.00;
CNY 100.01 becomes CNY 80.01.

## What should the agent ask?

If the source only said “orders over 100 get 20 off,” the agent should ask:
“Does exactly 100 qualify? Is the threshold based on merchandise subtotal or
an amount including shipping?” It should obtain the rule before choosing an
expected result. This example already answers both questions in R1 and R3.

The five cases illustrate selected rules. They do not claim complete coverage
of a real checkout, coupon consumption, refunds, concurrency, or security.

## 简体中文

这是人工编写的小型教学样例，用来展示需求如何对应到测试点和用例。
这里的文件是预览，不是已校验的 TestSpec change、Agent 实跑产物或产品通过测试的证据。

安装完整 TestKit 插件，在 Agent 中打开可写项目，附上 [requirements.md](requirements.md)，然后输入：

```text
使用 TestKit 根据这份需求创建 coupon-discount 测试变更。
完成需求分析、澄清缺失规则、测试点、用例生成和评审。
Python 依赖可用时导出 Excel。本次不执行测试。
保留各阶段前置条件和评审发现，不跳过必要步骤。
```

需要 Agent 本身的模型访问能力；Excel 导出还需要[Python 依赖](../../docs/installation.md#安装-python-依赖)。
本次设计不需要额外 API 账号、浏览器服务或设备。

阅读顺序：[需求规则](requirements.md) → 门槛、减免金额、过期和已使用券测试点 → [五条用例预览](cases.md)。
例如 R1 → TP-01（门槛边界）→ TC-01/02/03：99.99 元不能用券，100.00 元应付 80.00 元，100.01 元应付 80.01 元。

实际使用时，Agent 应在 `testspec/changes/coupon-discount/` 生成提案、需求、分析、测试点、JSON 用例、可选 Excel 和评审，
并维护必要的上下文元数据。这些预览文件不能替代阶段产物。

如果原需求只写“满 100 减 20”，Agent 应先询问：是否包含恰好 100？门槛是商品小计还是含运费金额？
本样例的 R1、R3 已给出答案。五条用例仅展示选定规则，不代表真实结算系统的全量覆盖；用券核销、退款、并发和安全测试均未展开。
