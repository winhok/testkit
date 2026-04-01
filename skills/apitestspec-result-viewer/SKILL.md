---
name: apitestspec-result-viewer
description: 在不重新执行测试的前提下消费已有 API 测试产物。只要用户主要想查看 allure-results、allure-report、结构化 JSON 结果、确认报告是否已生成、把已有 allure-results 转成可看报告、排查为什么报告打不开、或判断仓库里有哪些现成结果可以直接看，都应优先使用这个 skill。当用户说"打开 Allure 报告""看看这次测试结果""报告打不开"时务必使用。
---

# API Result Viewer

基于已有测试结果生成或打开报告，并指出结构化结果文件位置。

## One-line Purpose

当前阶段只负责消费已有测试产物，不负责重新执行。

## Use This When

- 用户说“打开 Allure 报告”“看看这次测试结果”“为什么报告打不开”
- 用户已经跑过测试，只想生成或查看报告
- 用户要确认仓库里是否存在 `allure-results`、`allure-report`、`reports/results.json` 之类的结果产物

## Do Not Use This When

- 用户要重新执行 spec 或查看新的 pass/fail 汇总。这属于 `apitestspec-scenario-runner`
- 用户要生成或改写 spec。这属于 `apitestspec-composer`
- 用户要补登录流、token、环境变量。这属于 `apitestspec-flow-configurator`
- 用户要从源码先盘点接口。这属于 `apitestspec-surface-scan`

## Hand Off To

- 缺少结果产物，需要先跑：`apitestspec-scenario-runner`
- 报告有了，但根因是 flow / env 缺失：`apitestspec-flow-configurator`

## Suite Routing Snapshot

详见 [套件路由表](../apitestspec-shared/references/routing.md)。本 skill 对应阶段 5（已有结果产物，只想看报告）。只要核心问题是“怎么看已有结果”就留在这里；如果核心问题变成“还没跑”或“跑不起来”，交回 `apitestspec-scenario-runner`。
## Agent Goal

目标是快速定位现有报告和结果产物，让用户马上看到已有结果，而不是把任务扩展成环境改造或重新执行。

## Decision Matrix

### 输入材料

- `allure-results`、`allure-report`、结构化 JSON 结果：进入本 skill
- 没有结果产物：通常不留在本 skill

### 允许动作

- 允许检查结果产物
- 允许生成静态报告
- 允许在用户需要时打开报告
- 不允许重新执行测试
- 不允许改 case、flow、`project.yaml`

### 完成标志

- 明确报告入口
- 明确结构化 JSON 结果路径
- 明确卡点是“缺产物”还是“缺 Allure CLI”

## Preferred Tools And Scripts

优先使用项目内脚本：

```bash
python skills/apitestspec-result-viewer/scripts/serve_report.py [--no-open]
```

仅当脚本不适用时，再直接执行 `allure generate` 或 `allure serve`。

## Default Artifact Paths

优先探测这些路径：

- `allure-results/`
- `allure-report/`
- `reports/results.json`
- `reports/summary.json`
- `reports/*.json`

如果这些路径都不存在，要明确说当前没有可消费产物，而不是假装可以继续。

## Execution Workflow

1. 先判断用户要“看已有结果”还是“重新跑测试”。
   - 只看结果：留在本 skill
   - 需要重新跑：交给 `apitestspec-scenario-runner`
2. 做环境探测。
   - 检查 `allure-results`
   - 检查 `allure-report`
   - 检查 Allure CLI
   - 检查结构化 JSON 结果
3. 根据用户意图选择路径。
   - 只生成静态报告：generate-only
   - 生成并打开：generate + open
   - 只是排查打不开：诊断模式
4. 输出可操作结论。
   - 报告入口
   - 结构化结果路径
   - 缺失项与下一步

## When To Stop Guessing

- `allure-results` 不存在时，不要假装可以生成报告
- Allure CLI 不存在时，不要偷偷安装
- 结构化结果文件不存在时，不要捏造路径
- 用户没有要求重新执行时，不要转成 runner 行为

## 未安装 Allure 时

不要擅自安装，只给引导：

- macOS：`brew install allure`
- 其他方式：参考 [references/install.md](references/install.md)
- 官方文档：https://docs.qameta.io/allure/

并明确说明：安装完成后，可在项目根目录执行 `allure serve allure-results`

## Output Contract

回答时必须说明：

- 是否检测到了 `allure-results`
- 是否检测到 `allure-report`
- 是否检测到 Allure CLI
- 实际执行的是“仅生成”还是“生成并打开”
- 结构化 JSON 结果的路径和用途
- 如果未能打开报告，明确卡在“缺结果产物”还是“缺 Allure CLI”
- 当前没有做什么：没有重新执行测试、没有修改 case/flow

## Resources

- 报告脚本：[scripts/serve_report.py](scripts/serve_report.py)
