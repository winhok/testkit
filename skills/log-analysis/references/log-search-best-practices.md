# Log Search Best Practices

用于设计日志检索方案、缩小查询范围、解释为什么搜不到或查询太慢。只在用户需要查询策略或当前证据不足时加载。

## 目录

- 查询前先定界
- 结构化字段优先
- 关联 ID 追踪
- 平台查询策略
- 高基数、索引与成本
- 采样、轮转与缺失日志
- 安全与脱敏
- 输出格式

## 查询前先定界

先回答这些问题，再写命令：

1. 用户要证明什么：失败根因、慢在哪里、字段在哪一跳丢、是否普遍发生、是否安全泄露。
2. 最小时间窗是什么：以用户报障时间为中心，先查小窗口，再按证据扩展。
3. 最小服务范围是什么：入口服务、疑似下游、数据库/缓存/消息消费者，不要一开始扫全平台。
4. 最可靠的 pivot 是什么：traceId/requestId/spanId、业务 ID、消息 ID、线程/worker、错误码、URL/任务名。
5. 当前日志来自哪里：本地文件、压缩归档、Kubernetes、ELK、Loki、Splunk、Datadog、Cloud Logging 或混合来源。

红旗：查询没有时间窗、没有服务范围、没有 pivot，却要求“把所有日志都搜一遍”。

## 结构化字段优先

结构化日志优先使用字段查询，而不是全文关键词：

| 目标 | 优先字段 |
|------|----------|
| 事件时间 | `timestamp`, `time`, `@timestamp`, `ObservedTimestamp` |
| 严重程度 | `severity`, `level`, `SeverityText`, `SeverityNumber` |
| 链路关联 | `traceId`, `trace.id`, `TraceId`, `requestId`, `correlationId`, `spanId` |
| 服务来源 | `service.name`, `service`, `app`, `module`, `logger`, `env`, `version` |
| 请求信息 | `http.method`, `path`, `route`, `status`, `duration_ms`, `client.ip` |
| 错误信息 | `error.type`, `error.message`, `exception`, `stack`, `code`, `reason` |
| 业务对象 | 订单、用户、任务、消息、批次等业务 ID 字段 |

如果日志是 JSONL，本地优先用 `jq` 精确筛选字段。若是混合文本，先识别格式比例，再分格式处理。

## 关联 ID 追踪

最佳 pivot 顺序：

1. trace/request/correlation/span id：跨服务最可靠。
2. 业务 ID、消息 ID、任务 ID、批次 ID：适合异步和跨线程。
3. 线程、worker、consumer partition：适合同一执行上下文，但要防线程复用。
4. 时间窗口 + 语义连续性：兜底，必须标注置信度。

分析时同时检查关联 ID 是否贯穿入口、服务层、依赖调用和响应/ack。断点本身就是日志质量问题；不要把“trace 断了”写成“调用没发生”。

## 平台查询策略

### 本地文件

- 首选 `rg -nH` 查普通文本；压缩归档用 `zgrep`。
- 大目录先定位文件名，再展开内容。
- JSONL 用 `jq -c 'select(...)'` 做字段筛选。
- 输出命令必须限制文件路径、时间窗或 pivot。

### Elasticsearch / ELK

- 优先字段查询：`trace.id`, `service.name`, `@timestamp`, `log.level`, `event.dataset`。
- 先按 service + time range + trace/request id 查精确链路，再按错误码或 endpoint 聚合。
- 不要建议把每个业务 ID 都提升为索引字段；只给高频查询且有明确保留价值的字段建索引。

### Grafana Loki

- 标签用于低基数来源维度，如 app、namespace、cluster、env、region。
- traceId、requestId、userId、orderId、timestamp 不应作为 Loki label；用日志内容过滤或 structured metadata。
- 查询先选 label stream，再用 `|=`, `|~`, `json`, `logfmt` 过滤字段。

### Splunk / Datadog / Cloud Logging

- 先限定 index/source/service/env/time，再按 trace/request id 或 JSON 字段过滤。
- Cloud Logging 结构化日志优先查 `jsonPayload.*`、`severity`、`trace`、`spanId`。
- Datadog/类似平台优先串联 logs、metrics、traces；只在需要诊断单请求时展开具体 trace。
- Splunk/类似平台优先使用已抽取字段，少用前缀很宽的全文搜索。

## 高基数、索引与成本

检查查询或日志设计是否踩到这些成本风险：

- 高基数字段：timestamp、traceId、requestId、userId、orderId、IP、pod instance、session id。
- 低价值高频日志：重复 debug、心跳、轮询、成功空操作。
- 低信息密度指标型事件：更适合 metrics，不一定适合长期索引日志。
- 采样策略：debug/成功请求可采样；错误、安全事件、审计事件不应被采样掉。

输出建议时区分“为了本次排查临时搜索”和“长期日志平台设计”。不要因为一次排查需要查 userId，就建议把 userId 做全局高基数标签。

## 采样、轮转与缺失日志

搜不到日志时逐项排查：

- 时间窗是否错了，跨服务时钟是否有偏差。
- 日志是否轮转到压缩文件或冷存储。
- 采样、丢弃规则、索引路由或保留期是否排除了目标日志。
- 服务名、环境、namespace、region 是否查错。
- traceId 是否只在部分服务注入，异步链路是否换成 messageId。
- 多行堆栈是否被拆成多条事件，导致异常上下文分散。

## 安全与脱敏

日志检索和引用都按最小必要原则：

- 不直接展示 token、cookie、Authorization header、密码、密钥、连接串、证件号、完整手机号、银行卡或完整地址。
- 用户输入进入日志查询命令时，注意换行、分隔符和 shell 特殊字符；必要时建议先复制为固定字符串再查。
- 发现敏感信息时，报告“日志脱敏风险”，不要在回复里扩大泄露范围。
- 安全事件和审计事件要保留 who/what/when/where/result/reason，避免只打印自然语言消息。

## 输出格式

给查询计划时使用：

```markdown
## 查询计划

目标：{要证明的问题}
范围：{服务/文件/平台}，{时间窗}
Pivot：{traceId/requestId/业务ID/错误码/endpoint}

1. `{query}`
   目的：{为什么先查这个}
   预期：{能证明或排除什么}

2. `{query}`
   目的：{为什么查这个}
   预期：{能证明或排除什么}

风险/注意：
- {高基数/采样/轮转/权限/脱敏/时钟偏差等}
```

只给能推进当前问题的查询。不要把所有平台的语法都列出来。
