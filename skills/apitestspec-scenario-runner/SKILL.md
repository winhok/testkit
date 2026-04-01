---
name: apitestspec-scenario-runner
description: 执行已有的框架原生 API spec，并返回明确的通过、失败和归因证据。只要用户已经有 cases.yaml、cases.json、Excel 或 CSV 用例，并且当前主要目标是运行、看 pass/fail、看失败原因、生成 allure-results 或结构化 JSON 结果，都应优先使用这个 skill。当用户说"跑一下""执行测试""看看哪些 case 挂了""直接跑别重写"时务必使用。
---

# API Scenario Runner

读取已有 API spec 并执行测试，产出 pass/fail、Allure 和结构化 JSON 结果。

## One-line Purpose

当前阶段只负责执行和归因，不负责设计 spec 或补 flow。

## Use This When

- 用户已经有 `.yaml`、`.yml`、`.json`、`.xlsx`、`.csv` 用例文件
- 用户要“跑一下”“执行”“验证”“看看哪些 case 挂了”
- 用户需要 pass/fail 汇总、失败 case 列表、失败原因分类
- 用户想生成 `allure-results`、结果 JSON 或静态报告前置产物

## Do Not Use This When

- 用户还没有原生 spec，主要目标是从文档生成 case。这属于 `apitestspec-composer`
- 用户主要问题是登录 flow、token、tenant、`project.yaml`、环境变量。这属于 `apitestspec-flow-configurator`
- 用户已经有结果产物，只想看报告。这属于 `apitestspec-result-viewer`
- 用户主要输入是源码，要先盘点接口。这属于 `apitestspec-surface-scan`

## Hand Off To

- 没有 spec：`apitestspec-composer`
- 缺 flow / env / 默认 headers：`apitestspec-flow-configurator`
- 执行完成后只想看报告：`apitestspec-result-viewer`

## Suite Routing Snapshot

详见 [套件路由表](../apitestspec-shared/references/routing.md)。本 skill 对应阶段 4（有 spec 且执行条件已具备，要运行）。本 skill 不能越界回头做前置阶段，只能明确指出缺什么并交接。
## Agent Goal

目标是自动决定“现在该怎么测”，真正执行，并把失败归因拆成可操作的类别，而不是只给一条命令，也不是把任务扩展成 case 设计或 flow 生成。

## Decision Matrix

### 输入材料

- 已有 spec：进入本 skill
- 兼容输入 `.xlsx` / `.csv`：可进入本 skill
- 没有 spec：不留在本 skill

### 允许动作

- 允许执行测试
- 允许读取 `project.yaml`、`config/.env`、结果产物
- 允许按需生成 `allure-results`
- 不允许自动改 spec
- 不允许顺手生成 flow 或 `project.yaml`

### 完成标志

- 说明执行是否真正发生
- 给出总 case 数、通过数、失败数
- 给出失败 case 与原因分类
- 明确产物路径或阻塞点

## Preferred Tools And Scripts

CLI 入口：

```bash
python skills/apitestspec-scenario-runner/scripts/run_tests.py \
  --project <project.yaml> \
  [--case <single-case-file>] \
  [--tag <tag>] \
  [--output results.json]
```

pytest 方式（支持 Allure）：

```bash
cd skills/apitestspec-scenario-runner/scripts && \
pytest test_api.py --project <project.yaml> [--tag <tag>] --alluredir=allure-results
```

## Unified Runtime Conventions

- 项目定义通常来自 `project.yaml`
- `BASE_URL` 可来自 `--base-url` 或环境变量
- 环境变量约定统一参考 `config/.env.example`
- 本 skill 不维护 `config/.env.example`，缺失时只诊断并交接

## Execution Workflow

1. 判断是否具备执行前提。
   - 有 spec：继续
   - 没有 spec 但有文档：转 `apitestspec-composer`
   - 有 spec 但依赖 flow / env：转 `apitestspec-flow-configurator`
2. 做执行前探测。
   - spec 文件是否存在
   - `project.yaml` 是否存在
   - 是否提供 `BASE_URL`
   - `config/.env` 是否存在
3. 选择最小执行路径。
   - 优先按用户给定 spec 直接执行
   - 只在用户要求时加 `--serve`
   - 只在用户要求过滤时加 `--case-id` 或 `--tag`
4. 执行后做失败归因。
   - 环境问题
   - 鉴权问题
   - flow 问题
   - 数据问题
   - 断言问题
   - 路径参数问题
5. 输出结论并交接。
   - 需要修 flow / env：交给 `apitestspec-flow-configurator`
   - 只需要消费结果：交给 `apitestspec-result-viewer`

## Auto-Detect Before Asking

- 自动识别 spec 类型：YAML、JSON、Excel、CSV
- 自动寻找默认 `project.yaml`
- 自动读取 `config/.env`
- 自动判断是否应该产出 Allure 结果

## When To Stop Guessing

- case 文件不存在时，不要假设路径正确
- 看不出依赖 flow 如何满足时，不要假装鉴权已配置好
- 失败原因证据不足时，不要把所有问题都归因给 case 设计
- 用户没要求修改 case 时，不要擅自改写 spec

## Output Contract

执行结束后，回答必须覆盖：

- 总 case 数、通过数、失败数
- 失败 case 的用例 ID 或可识别名称
- 每个失败 case 的简要原因
- 失败原因分类，例如环境、鉴权、flow、断言、路径参数、数据问题
- 具体修改建议
- 实际使用的规格文件、项目配置文件和关键命令
- 结果产物位置，例如 `allure-results/` 或结构化 JSON 结果
- 若因环境或配置导致未能真正执行，要明确停在哪一步
- 当前没有做什么：没有改 spec、没有补 flow、没有直接查看报告

## Resources

- Spec 格式参考：[../apitestspec-shared/references/spec-format.md](../apitestspec-shared/references/spec-format.md)
- 完整示例项目：[../apitestspec-shared/references/example-project.md](../apitestspec-shared/references/example-project.md)
- 执行引擎：[scripts/engine.py](scripts/engine.py)
- 文件加载器：[scripts/loaders.py](scripts/loaders.py)
- CLI 入口：[scripts/run_tests.py](scripts/run_tests.py)
- pytest 适配：[scripts/conftest.py](scripts/conftest.py) + [scripts/test_api.py](scripts/test_api.py)
