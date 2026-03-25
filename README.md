# TestKit

一套 Agent Skills 测试工具集，用于在 AI 辅助下完成软件测试工作。兼容 Claude Code、Cursor、Trae 等支持 SKILL.md 的 AI 编码助手。

## 包含的 Skills

### testspec - 测试用例设计

从需求分析到测试用例生成的完整流程。

```
testspec-new → testspec-analysis → testspec-points → testspec-generate → testspec-review
  创建变更       需求深度分析         提炼测试要点       生成测试用例        用例评审
```

| Skill | 说明 |
|-------|------|
| testspec-new | 新建测试工作，创建变更目录和测试提案（proposal.md） |
| testspec-analysis | 需求深度分析，识别测试风险和边界，产出 requirements-analysis.md |
| testspec-points | 从分析结论中提炼测试点清单（specs/testpoints.md） |
| testspec-generate | 根据测试点生成完整测试用例，导出 Excel（.xlsx）或 XMind（.xmind） |
| testspec-review | 用例评审，对生成的测试用例做交叉验证，产出评审报告（review-report.md） |

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
# testspec 生成 Excel 格式用例
pip install openpyxl

# api2jmx 解析 YAML 格式 OpenAPI 文档
pip install pyyaml
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
```

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

## License

MIT
