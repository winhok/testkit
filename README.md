# TestKit

一套 Agent Skills 测试工具集，用于在 AI 辅助下完成软件测试工作。兼容 Claude Code、Cursor、Trae 等支持 SKILL.md 的 AI 编码助手。

## 包含的 Skills

### testspec - 测试用例设计

从需求分析到测试用例生成的完整流程。

```
testspec-new → testspec-analysis → testspec-points → testspec-generate → testspec-review → testspec-publish
  创建变更       需求深度分析         提炼测试要点       生成测试用例        用例评审        用例入库(可选)
```

| Skill | 说明 |
|-------|------|
| testspec-new | 新建测试工作，创建变更目录和测试提案（proposal.md） |
| testspec-analysis | 需求深度分析，识别测试风险和边界，产出 requirements-analysis.md。自动检索 testlib 已有覆盖 |
| testspec-points | 从分析结论中提炼测试点清单（specs/testpoints.md） |
| testspec-generate | 根据测试点生成完整测试用例，导出 Excel（.xlsx）或 XMind（.xmind） |
| testspec-review | 用例评审，对生成的测试用例做交叉验证，产出评审报告（review-report.md） |
| testspec-publish | 将评审通过的用例发布到 testlib 知识库，按模块/功能自动分类、增量合并 |

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
# testspec 生成 Excel 格式用例 / apitestspec 导入导出 Excel
pip install openpyxl

# api2jmx 解析 YAML 格式 OpenAPI 文档 / apitestspec 加载配置
pip install pyyaml

# apitestspec 执行 HTTP 请求
pip install requests

# apitestspec 生成 Allure 报告（需单独安装 Allure CLI）
pip install allure-pytest
```

## 使用

### testspec

```
testspec-new 用户登录
testspec-analysis
testspec-points
testspec-generate Excel
testspec-generate XMind
testspec-review
testspec-review --deep
testspec-publish
```

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
├── skills/                              # 所有 AI Skills
│   ├── testspec-new/                    # 测试用例设计流程
│   ├── testspec-analysis/
│   ├── testspec-points/
│   ├── testspec-generate/
│   ├── testspec-review/
│   ├── testspec-publish/                # 用例入库到知识库
│   ├── testspec-shared/                 # testspec 共享协议与契约
│   ├── api2jmx/                         # API 文档转 JMX
│   ├── log-analysis/                    # 日志分析
│   ├── sql-safety-review/               # SQL 安全评估
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
