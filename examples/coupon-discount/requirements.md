# Coupon discount requirements / 优惠券需求

Synthetic teaching input, revision 1. / 虚构教学需求，第 1 版。

| ID | English | 简体中文 |
|---|---|---|
| R1 | Amounts use CNY with two decimal places. A merchandise subtotal of at least CNY 100.00 qualifies for one valid coupon deducting CNY 20.00. Below the threshold, reject the coupon and leave the subtotal unchanged. | 金额以人民币元计，保留两位小数。商品小计满 100.00 元，一张有效券减 20.00 元；不足门槛则拒绝使用，小计不变。 |
| R2 | Reject an expired or already-used coupon, even when the subtotal qualifies, and leave the subtotal unchanged. | 已过期或已使用的券，即使金额达标也不可用，小计不变。 |
| R3 | Shipping and stacking discounts are outside scope. | 运费和优惠叠加不在范围内。 |

For the cases, coupon status is a supplied fixture: valid, expired, or already-used.
Time calculation and coupon consumption are not specified by this teaching input.

用例中的券状态是给定测试数据：有效、已过期、已使用。本教学需求未定义过期时间计算和核销过程。
