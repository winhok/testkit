---
name: perfspec-analysis
license: MIT
description: 分析性能测试需求与风险，复用当前 TestSpec、业务流程和已有 SLO，明确目标、范围、性能口径及关键缺口。用户要梳理性能需求、容量问题或压测前需要哪些信息时使用；明确的性能计划、脚本生成、执行和结果评估分别交给其他 perfspec 阶段。
---

# PerfSpec：需求分析

将业务问题转成可追溯的性能目标，产出分析和待确认项，不执行请求。

## 输入与路由

读取用户指定的 PRD、TestSpec requirements/analysis/strategy、已复核 API 契约或业务流程描述。只读相关材料；缺少 TestSpec 不强制创建完整 change。
读取 [生命周期与来源规则](../_perfspec-shared/references/lifecycle.md)。需要字段定义时读取 [需求与计划契约](../_perfspec-shared/references/plan-contract.md)。
只要求分析已有结果时交给 `perfspec-evaluate`；只要求普通功能需求分析时使用 `testspec-analysis`。

## 分析

1. 复用已确认的范围、环境、业务规则和 SLO，记录来源位置与摘要。区分当前需求、生产流量观测、历史报告和建议，不把历史阈值自动升级为当前标准。
2. 明确要回答的问题：预期负载下可靠性、容量上限、突增恢复、长期稳定性或版本性能回退。说明成功结论只覆盖哪些场景。
3. 用完整业务旅程定义场景：角色、鉴权、请求顺序、动态关联、成功 oracle 和副作用。API 返回 202 时，以业务约定的可观察完成条件定义旅程完成。
4. 澄清目标是并发用户、业务迭代到达率还是请求速率；记录业务配比、每迭代请求数、think time、数据消耗和环境代表性。
5. 将延迟指标明确到请求或旅程、样本范围、单位、时间窗及失败样本是否计入。P95/P99、错误率、吞吐和完成率各自记录来源；未知值保留 unknown，不发明默认 SLA。
6. 只询问会改变计划或结论的缺口。已有授权和回答持续有效，不要求重复口令确认。可先写 draft 分析；负载、目标或判定口径未定时，列 blocker，禁止包装成可执行计划。

## 输出

在明确的 `perfspec/<spec-id>/` 中写 `analysis.md` 与 `requirements.json`，结构见共享契约。
包含 scope/out-of-scope、目标及依据、场景/需求 ID、候选工具理由、已确认事项、建议和 blocker。建议阈值标记 proposed；只有来源或用户决策支持才能标 confirmed。
只写分析产物，不改 TestSpec context、TestLib、产品需求或既有冻结运行。

## 交付

报告确认了什么、什么仍未知、能否进入 `perfspec-plan`。不宣称工具可用、数据已就绪或性能已通过。
