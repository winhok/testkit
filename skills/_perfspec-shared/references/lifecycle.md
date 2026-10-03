# PerfSpec 生命周期与来源

五个独立入口：analysis → plan → generate → run → evaluate。已有完整输入可直接进入对应阶段；数据准备和诊断是条件分支。阶段不会自动授权下一阶段。

## 工作区

目标项目中维护 `perfspec/<spec-id>/analysis.md`、`requirements.json`、`plan.json`、`plan.md`、`asset-manifest.json` 与 `assets/<runner>/`。spec-id 是稳定测试意图标识，不是执行 ID。相对路径以显式项目 root 解析，禁止越界路径。
运行使用 `test-runs/<run-id>/`，每次新 profile/重试独立目录；既有记录不可覆盖。执行快照含规范、计划、资产和数据/生成器及有效配置，原始结果与评估产物位于运行目录。

## 来源

PerfSpec 不改变 TestSpec context v2、case schema 或现有 API result。复用相关 REQ/case/strategy ID、source_revision 和摘要；当前 TestSpec 材料先通过现有链验证。不能让代码现状、历史工具默认值、社区示例成为产品标准。
无 TestSpec 的局部性能检查使用 local；正式 acceptance 必须具备当前需求、用例、策略与全范围映射。publish 不是执行前置。
requirements/plan 标记 draft 或 ready；ready 仅意味着该产物关键决策确定，不能代表有执行授权。unknown/proposed/confirmed 明确区分。上游内容改变，下游标 stale，冻结运行保留原貌。

## 社区依据

以下链接是设计依据，按需查对应版本，不整套搬入外部框架或 Agent Skill：

- [Taurus execution](https://gettaurus.org/docs/ExecutionSettings/)：场景、负载和多执行器分离，可引用原生脚本；工具能力并不完全相同。
- [k6 automation](https://grafana.com/docs/k6/latest/testing-guides/automated-performance-testing/)：先 smoke、建立负载基线、复用业务场景。
- [k6 open/closed](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/)：负载调度语义。
- [JMeter best practices](https://jmeter.apache.org/usermanual/best-practices.html)：CLI、轻量监听、压测机资源。
- [Locust throughput](https://docs.locust.io/en/stable/increasing-request-rate.html)：用户数、spawn rate、压测机瓶颈。
- [Prometheus histograms](https://prometheus.io/docs/practices/histograms/)：分位数不可平均，聚合保留分布。

TestKit 本地契约是项目设计；不声称以上社区已有同名 PerfSpec 标准。参考代码、模板和商业默认负载不属于产品验收依据。
