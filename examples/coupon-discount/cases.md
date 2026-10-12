# Case preview / 用例预览

Manually authored illustration; all cases are **not run**. This table is not the
TestSpec JSON schema or a test execution report.

人工编写的教学预览，所有用例均为**未执行**；本表不是 TestSpec JSON 格式或执行报告。

Common setup: use CNY amounts and one coupon with the specified status; exclude
shipping and other discounts. For each row, set the merchandise subtotal and
coupon status, then attempt to apply the coupon once.

共同前置条件：使用人民币金额和一张指定状态的券，不含运费及其他优惠。
每行步骤：设置商品小计与券状态，尝试使用一次优惠券。

| Case / 用例 | Requirement / 需求 | Test point / 测试点 | Subtotal / 小计 | Coupon / 券状态 | Expected / 预期 |
|---|---|---|---|---|---|
| TC-01 | R1 | TP-01: threshold / 门槛 | 99.99 | Valid / 有效 | Reject; unchanged 99.99 / 拒绝，小计不变 |
| TC-02 | R1 | TP-01: threshold / 门槛 | 100.00 | Valid / 有效 | Accept; payable 80.00 / 成功，应付 80.00 |
| TC-03 | R1 | TP-01: threshold / 门槛 | 100.01 | Valid / 有效 | Accept; payable 80.01 / 成功，应付 80.01 |
| TC-04 | R2 | TP-02: expired / 过期券 | 100.00 | Expired / 已过期 | Reject; unchanged 100.00 / 拒绝，小计不变 |
| TC-05 | R2 | TP-03: used / 已使用券 | 100.00 | Already-used / 已使用 | Reject; unchanged 100.00 / 拒绝，小计不变 |

R3 defines the scope exclusion; it is not a tested feature in this preview.
R3 限定排除范围，本预览不把它计作已测试功能。
