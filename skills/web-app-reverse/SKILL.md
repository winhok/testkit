---
name: web-app-reverse
license: MIT
description: 面向拿不到代码仓库的测试工程师，分析网站已交付的 HTML、JS/CSS、公开 source map、浏览器状态和运行记录，逆向建立页面、路由、资源、接口、状态与角色分支的全局测试地图，为 TestSpec 分析、测试点和用例设计提供实现证据。用户说没源码、无仓库、逆向 Web、分析打包 JS/bundle、梳理线上网站全貌、找隐藏测试面或判断测哪里时使用；按已确认用例执行验收走 app-test，有源码的实现校准走 testspec-code-calibrate，主动安全探测不使用本 skill。
---

# Web 应用逆向侦察

目标是给测试设计提供可追溯的实现地图。输入网站已交付或用户导出的浏览器产物，不要求源码、数据库或服务器权限。

**核心约束：逆向线索只能产生候选与覆盖边界；没有运行证据时，不能把资源中存在的路径、组件或分支写成线上可用功能。**

读取 [inspection.md](references/inspection.md)，按其中的覆盖账本和六层地图工作。需要登记本次运行证据时再读取 [共享执行契约](../_test-run-shared/references/execution-contract.md)；只分析交付物和已有记录时无需创建验收 scope。

- [ ] **Step 1 ⚠️ REQUIRED — 范围：**明确目标 origin、入口页面、角色、环境、已有产物，以及允许的只读导航和禁止的业务动作；信息缺失但不影响现有产物分析时记为未知项。
- [ ] **Step 2 ⚠️ REQUIRED — 盘点：**记录已扫描、跳过、缺失和仅被引用的资源，区分引用边数量与唯一资源数量；分母未知时不得给覆盖百分比。
- [ ] **Step 3 ⚠️ REQUIRED — 建图：**从 HTML 入口、static/dynamic import、chunk、worker 和 source map 建资源关系，再提取页面/路由、接口/实时通道、状态、角色/功能开关、校验和错误分支。
- [ ] **Step 4 ⚠️ REQUIRED — 归并：**用 origin、跨文件共现和 locator 合并同一功能线索；保留来源冲突、第三方边界、死代码候选与证据等级。
- [ ] **Step 5 条件分支 — 补充证据：**可以消费用户提供的 HAR、Network、trace 或浏览器状态；为补齐已交付资源可做无副作用的页面加载和只读导航。逆向阶段不执行提交表单、写业务数据、重放写请求或故障注入，而是把对应行为链、前置条件、oracle 和证据缺口写成测试设计输入。
- [ ] **Step 6 ⚠️ REQUIRED — 交付：**输出范围与覆盖账本、六层全局地图、候选测试点、风险优先级、证据等级、未知项和最小验证建议。已有 TestSpec change 时交给 `testspec-analysis`；尚无 change 时先由 `testspec-new` 建立 PRD-first 上下文，再进入 analysis 和后续主流程。

已有完整导出目录可运行 `python scripts/inspect_assets.py --root <exports> --discover-local --site-origin <origin> --output <asset-inventory.json>`；只分析指定文件时改用一个或多个 `--asset <relative-path>`。脚本最多自动盘点 200 个本地支持文件，可用 `--max-assets` 调整；它不访问网络、不下载引用，输出是待人工归并的中间 inventory，不是最终结论。

默认交付使用 `inspection-report.md` 的结构；不适合写文件时在回复中使用相同章节。用户要求结构化结果时提供 `inspection-map.json`，顶层固定为 `schema_version`、`scope`、`coverage`、`maps`、`findings`、`unknowns`。详细字段见 inspection.md。

本 skill 在无仓库时承担与可选代码证据相同的上游发现职责，但不伪装成 `code_evidence` 或 `artifacts/code-calibration.json`。交付前确认：每个结论有文件/URL、行号或浏览器 locator；每个测试点能追溯到触发线索；相同 path 的不同 origin 未合并；source map 与 bundle 版本已关联或注明未知；报告明确没有拿到的 lazy chunk、角色与页面。发现作为 TestSpec 的 `reference` 输入，产品规则冲突交由产品确认，不自行改 canonical requirements。
