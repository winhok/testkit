# TestKit

一套 Agent Skills 测试工具集，用于在 AI 辅助下完成软件测试工作。兼容 Claude Code、Cursor、Trae 等支持 SKILL.md 的 AI 编码助手。

## 包含的 Skills

### testspec - 测试用例设计

从需求分析到测试用例生成的完整流程。

```
testspec-new → testspec-update(可选/可重复) → testspec-analysis → testspec-points → testspec-generate → testspec-review → testspec-publish
  创建变更       需求源口径收敛              需求深度分析        提炼测试要点       生成测试用例        用例评审        用例入库(可选)

历史资料分支：testspec-import（隔离导入）→ 当前 PRD 对齐 → 主流程
代码证据分支：显式 testspec-code-calibrate → 快照对齐/分支 Diff/恢复草稿 → 产品确认或主流程
知识库维护分支：testspec-audit（只读审计）→ 用户确认 lifecycle proposal → 受控修复
```

TestSpec 默认采用 PRD-first：当前 PRD、产品回答和验收规则是主基线。代码不是默认输入，只在用户明确提供路径、要求调查或授权作为已上线行为基线时用于校准；没有代码权限不会阻断流程。TestLib 历史内容只能提供回归提示、命名和表达风格，不能覆盖当前 PRD。

| Skill | 说明 |
|-------|------|
| testspec-new | 新建测试工作，创建变更目录和测试提案（proposal.md） |
| testspec-code-calibrate | 显式授权后提取代码中的可观察行为，比较 PRD、追踪生产/测试/需求分支 Diff，或生成非 canonical 恢复草稿；不直接修改 requirements.md |
| testspec-import | 将历史 Excel/CSV/JSON/Markdown/TXT/XMind 用例隔离导入为 `legacy-import + unverified`，并生成 `imports/reconciliation.json`，不直接写 TestLib |
| testspec-update | 已有变更的 PRD/API/UI/产品回答口径收敛，更新 requirements.md 并标记旧下游产物 |
| testspec-analysis | 需求深度分析，识别测试风险和边界，产出 requirements-analysis.md。自动检索 testlib 已有覆盖 |
| testspec-points | 从分析结论中提炼测试点清单（specs/testpoints.md） |
| testspec-generate | 根据测试点生成完整测试用例，导出 Excel（.xlsx）或 XMind（.xmind） |
| testspec-review | 用例评审，对生成的测试用例做交叉验证，产出评审报告（review-report.md） |
| testspec-publish | 将评审通过的用例发布到 testlib 知识库，按模块/功能自动分类、增量合并 |
| testspec-audit | 只读审计 TestLib 的重复、错放、来源缺失和未验证历史导入，默认只提 lifecycle proposal |

### api2jmx - API 文档转 JMX 测试脚本

根据 API 接口文档（OpenAPI/Swagger 或 Markdown 格式）自动生成 Apache JMeter 的 JMX 测试脚本。

- 支持 OpenAPI 3.0 / Swagger 2.0（YAML/JSON）
- 支持 Markdown 格式的 API 文档（多种常见格式）
- 生成包含 HTTP 请求、参数、断言的完整测试计划

### log-analysis - 服务端日志智能分析

将混杂的服务端日志拆解为可读的链路视图，还原请求/任务的完整生命周期，识别异常和性能瓶颈，产出结构化分析报告。

- 支持应用日志、慢查询日志、Nginx access log、Kafka 消费日志、定时任务日志等
- 按 traceId / 线程自动拆分链路，还原请求时间线
- 提供 grep 深挖命令辅助继续排查

### sql-safety-review - SQL 查询安全评估

评估 SQL SELECT 查询是否存在炸库风险（全表扫描、大范围扫描、排序/临时表开销），给出改写方案。

- 结论先行：第一行给出风险等级和能不能跑的结论
- 引导通过 EXPLAIN 和表结构做精确诊断
- 缺少信息时默认保守，按中高风险处理

### android-static-app-reverse - Android 应用静态逆向分析（测试工具）

测试团队专用的 Android APK 静态逆向分析工具，用于接口发现、客户端安全评估和兼容性验证等测试场景。本工具是 TestKit 测试工具集的一部分，仅执行纯静态分析，不涉及任何绕过、破解或运行时攻击行为。

- 支持 ADB 导出安装包（自动处理 split APK）
- 支持 JADX、apktool、dex2jar + Vineflower 多引擎反编译
- APKiD 加固/保护检测，apkleaks 接口/密钥泄露扫描
- 自动识别 Retrofit/OkHttp/Volley/WebView 等网络栈并提取 API 端点
- 产出覆盖度和置信度标注的结构化分析报告

> ⚠️ 合规声明：本工具属于测试工具集，仅限在授权范围内用于安全测试、质量验证和接口发现。严禁用于非法逆向、破解、绕过付费/授权机制或侵犯知识产权等行为。使用者须确保已获得被测应用的合法测试授权。

### apitestspec - API 接口自动化测试

从接口扫描到测试执行的完整 API 自动化测试链路，5 个 skill 按"最早缺失产物优先"路由。

```
apitestspec-surface-scan → apitestspec-composer → apitestspec-flow-configurator → apitestspec-scenario-runner → apitestspec-result-viewer
     源码扫描接口             文档转可执行 spec         配置前置 flow                    执行测试                    查看报告
```

| Skill | 说明 |
|-------|------|
| apitestspec-surface-scan | 扫描后端源码发现 HTTP API，输出 Markdown/JSON 接口清单 |
| apitestspec-composer | 将接口文档/OpenAPI 转成框架原生 API spec（YAML/JSON），按需导出 Excel/CSV |
| apitestspec-flow-configurator | 配置登录、token、tenant 等前置 flow 和项目级默认请求配置 |
| apitestspec-scenario-runner | 执行已有 API spec，产出 pass/fail、Allure 和结构化 JSON 结果 |
| apitestspec-result-viewer | 消费已有测试产物，生成/打开 Allure 报告 |

## 安装

### Codex

本仓库现在包含 Codex 插件 manifest：

- `.codex-plugin/plugin.json` — 单插件仓库入口，直接引用 `./skills/`
- `.agents/plugins/marketplace.json` — 本地 marketplace 示例，指向 `./plugins/testkit`
- `plugins/testkit/` — marketplace 入口目录，通过符号链接复用根目录的 manifest、skills 和 assets，避免维护两份技能内容

本地验证：

```bash
python scripts/test_all.py
```

### Claude Code（推荐）

```
/plugin marketplace add winhok/testkit
/plugin install testkit
```

安装后重启 Claude Code 加载新 skills。

### Cursor

通过 Settings UI：

1. 打开 Settings（`Cmd+Shift+J` / `Ctrl+Shift+J`）
2. 进入 Rules → Add Rule → Remote Rule (GitHub)
3. 输入：`https://github.com/winhok/testkit.git`

### Trae

1. 打开 Settings → Rules & Skills
2. 导入本仓库中 `skills/` 下各目录的 `SKILL.md` 文件

### 手动安装（通用）

```bash
# Claude Code
git clone git@github.com:winhok/testkit.git .claude/skills/testkit

# Cursor
git clone git@github.com:winhok/testkit.git .cursor/skills/testkit

# Trae
git clone git@github.com:winhok/testkit.git .trae/skills/testkit
```

### Python 依赖

```bash
pip install -r requirements.txt
```

或按需单独安装：

```bash
# testspec 生成 Excel 格式用例 / apitestspec 导入导出 Excel
pip install openpyxl

# api2jmx 解析 YAML 格式 OpenAPI 文档 / apitestspec 加载配置
pip install pyyaml

# apitestspec 执行 HTTP 请求
pip install requests

# apitestspec 生成 Allure 报告（需单独安装 Allure CLI）
pip install allure-pytest
```

## 验证

```bash
# 全量稳定检查：插件包装、契约校验、脱敏 eval 定义、脚本单测
python scripts/test_all.py

# 只检查 Codex 插件包装
python scripts/test_all.py --only packaging

# 只检查 testspec 跨 skill 契约
python scripts/test_all.py --only contracts

# 只检查 TestSpec eval 的合成数据声明、确定性 fixtures 和上下文链验证器
python scripts/test_all.py --only evals

# 只跑当前可稳定执行的脚本单测
python scripts/test_all.py --only unit
```

TestSpec eval 只允许提交标记为 synthetic 的内联 fixture；本地真实业务材料应放在已忽略的 `testspec/` 或 `skills/**/evals/private/`，不得复制到公开 eval JSON。校验器还会拒绝用户主目录绝对路径、邮箱、IP、UUID、非 `example.invalid` URL 和编辑器聊天记录路径标记。该检查验证 eval 定义和确定性断言，模型行为 eval 仍由支持 `evals/evals.json` 的运行器执行。

### testlib 维护

`testspec-publish` 负责把评审通过的用例入库；下面脚本用于后续维护 `testspec/testlib/`，不会替代发布流程。审计默认只读，任何合并、废弃或迁移都需要用户确认具体 case ID。

```bash
# 只读校验 testlib 健康度，输出 JSON 报告
python skills/_testspec-shared/scripts/validate_testlib.py --testlib testspec/testlib

# 组合检查结构健康、重复、错放和 provenance 风险；不会自动修复
python skills/testspec-audit/scripts/audit_testlib.py --testlib testspec/testlib

# 从 modules/*/*.json 重建 index.json 和 .testlib.json
python skills/_testspec-shared/scripts/rebuild_testlib_index.py --testlib testspec/testlib
```

## 使用

### testspec

```
testspec-new 用户登录
testspec-code-calibrate
testspec-import legacy-cases.xlsx
testspec-update
testspec-analysis
testspec-points
testspec-generate Excel
testspec-generate XMind
testspec-review
testspec-review --deep
testspec-publish
testspec-audit
```

`testspec-import` 只写变更目录下的隔离产物；旧用例必须在 `imports/reconciliation.json` 中按当前 PRD 对齐，再经过 analysis/points/generate/review 生成新的原生用例。`legacy-import + unverified`，以及缺少、为空、枚举未知或组合非法的 `origin/trust`（`provenance-unknown`）都会被 review/publish 无条件阻断。

`testspec-code-calibrate` 默认禁止隐式调用，只有用户明确授权代码角色、ref/commit 和仓库内相对 scope 后才读取代码（显式授权整个仓库时 scope 可为 `.`）。comparison 对照完整实现快照；change-diff 对生产/测试/需求等显式分支做静态变更追踪并生成脱敏 `change-snapshot.json`；recovery 生成显著标为非 canonical 的实现行为草稿。三种模式都生成经过验证的 `code-calibration.json` 和 snippet-free Markdown view。任何代码与产品意图的冲突都必须先产品确认，再由 `testspec-update` 收敛到 requirements.md。

testspec-publish 会将评审通过的用例自动分类到 `testlib/modules/<模块>/<功能>.json`，生成 changelog，更新统计。建议配合独立的测试知识库 Git 仓库使用。

### api2jmx

```
api2jmx openapi.yaml
api2jmx api_doc.md
```

### log-analysis

```
# 直接粘贴日志文本让 AI 分析
# 或提供日志文件路径
分析一下 /data/services/app/logs/app.log 最近的报错
这段日志帮我看看为什么接口超时
```

### sql-safety-review

```
# 贴一条 SELECT 语句
这条 SQL 能不能在生产跑？
SELECT * FROM orders WHERE status = 1
```

### android-static-app-reverse

```
# 从手机导出并反编译指定应用
帮我把手机上的 com.example.app 导出来反编译

# 分析本地 APK 文件
逆向分析一下 /tmp/sample.apk

# 提取接口端点
帮我提取这个 APK 里的 API 接口

# 检测加固
看看这个应用有没有加固
```

### apitestspec

```
# 扫描源码接口
帮我扫描一下 src/main/java 里的接口

# 从接口文档生成可执行 spec
根据这份 API 文档生成测试用例

# 配置前置 flow
帮我配一下登录 flow 和 token 提取

# 执行测试（CLI）
python skills/apitestspec-scenario-runner/scripts/run_tests.py --project my_project/project.yaml

# 执行测试（pytest + Allure）
cd skills/apitestspec-scenario-runner/scripts && pytest test_api.py --project my_project/project.yaml --alluredir=allure-results

# 查看报告
帮我看看这次测试结果
```

## 项目结构

```
testspec/
├── .codex-plugin/plugin.json           # Codex 插件 manifest
├── .agents/plugins/marketplace.json    # Codex 本地 marketplace 示例
├── assets/                             # 插件展示资产
├── plugins/testkit/                    # marketplace 指向的插件入口（复用根目录内容）
├── scripts/test_all.py                 # 仓库级验证入口
├── skills/                              # 所有 AI Skills
│   ├── testspec-new/                    # 测试用例设计流程
│   ├── testspec-update/                 # 需求源口径收敛
│   ├── testspec-analysis/
│   ├── testspec-points/
│   ├── testspec-generate/
│   ├── testspec-review/
│   ├── testspec-publish/                # 用例入库到知识库
│   ├── _testspec-shared/                # testspec 共享协议与契约
│   ├── api2jmx/                         # API 文档转 JMX
│   ├── log-analysis/                    # 日志分析
│   ├── sql-safety-review/               # SQL 安全评估
│   ├── android-static-app-reverse/      # Android 静态逆向分析（测试工具）
│   ├── apitestspec-surface-scan/        # API 自动化：源码扫描
│   ├── apitestspec-composer/            # API 自动化：文档转 spec
│   │   └── scripts/                     # bootstrap, excel/csv 导出
│   ├── apitestspec-flow-configurator/   # API 自动化：前置 flow
│   │   └── scripts/                     # bootstrap_flow
│   ├── apitestspec-scenario-runner/     # API 自动化：执行引擎
│   │   └── scripts/                     # engine, loaders, pytest adapter
│   ├── apitestspec-result-viewer/       # API 自动化：报告查看
│   │   └── scripts/                     # serve_report
│   └── apitestspec-shared/              # API 自动化：共享参考文档
│       └── references/                  # spec-format.md, example-project.md
└── README.md
```

## License

MIT
