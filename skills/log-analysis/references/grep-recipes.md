# Grep / rg / jq Recipes

只在当前日志无法闭环时加载。选择最少命令，不要把所有命令都输出。

## 规则

- 优先限制 trace/correlation id、业务 id、时间窗口、文件路径。
- 普通日志优先用 `rg`；若不可用再用 `grep`。压缩日志用 `zgrep`。
- JSONL/结构化日志优先用 `jq` 按字段筛选，不要只做全文关键词搜索。
- 大范围扫描必须加 `timeout`、`nice` 或等价保护；能用文件名定位就不要直接输出内容。
- 每条命令后写“为什么查这个”。
- 占位符必须替换成用户场景中的真实字段或保留明显占位符，不要编造路径。

## 常用命令

### 追踪同一关联 ID

```bash
rg -nH --fixed-strings '{trace_or_correlation_id}' /path/to/service.log
```

为什么查这个：补齐同一请求或任务在当前片段外的上下文。

`rg` 不可用时：

```bash
grep -nH '{trace_or_correlation_id}' /path/to/service.log
```

为什么查这个：同上，作为兼容兜底。

### 在时间窗内查错误和异常

```bash
rg -nH 'ERROR|WARN|Exception|Caused by|timeout|failed' /path/to/service.log | rg '{time_prefix_or_window}'
```

为什么查这个：确认核心时间窗附近是否还有未提供的失败信号。

### 追踪业务实体或消息 ID

```bash
rg -nH --fixed-strings '{business_or_message_id}' /path/to/log/root
```

为什么查这个：当异步或跨线程缺少 trace id 时，用业务实体串联链路。

### 查看同一线程或 worker 的上下文

```bash
rg -nH --fixed-strings '{thread_or_worker_name}' /path/to/service.log | rg '{time_prefix_or_window}'
```

为什么查这个：判断同一执行上下文内请求、任务或消息的边界。

### 追踪字段流转

先查字段名和已知别名：

```bash
rg -nH '{field_name}|{alias_1}|{alias_2}' /path/to/service.log | rg '{trace_or_time_window}'
```

为什么查这个：确认字段在哪一跳出现、变空、改名或消失，避免先展开大量请求体/响应体。

字段名没有命中、但必须判断请求体或响应体是否打印过时，再扩大到载荷关键词：

```bash
rg -nH 'payload|body|params|request|response' /path/to/service.log | rg '{trace_or_time_window}'
```

为什么查这个：只在字段名缺失时定位可能承载字段的载荷日志，仍然用 trace 或时间窗限制范围，降低噪音和敏感信息暴露。

### JSONL 按 trace 精确筛选

```bash
jq -c 'select(.traceId == "{trace_id}" or .["trace.id"] == "{trace_id}" or .requestId == "{trace_id}")' /path/to/service.jsonl
```

为什么查这个：结构化日志用字段筛选比全文匹配更准确，可避免误命中消息体里的相似字符串。

### JSONL 查错误和慢调用

```bash
jq -c 'select((.level == "ERROR" or .severity == "ERROR" or (.duration_ms // 0) > {threshold_ms}) and (.timestamp >= "{start}" and .timestamp <= "{end}"))' /path/to/service.jsonl
```

为什么查这个：在时间窗内同时定位显式错误和超过阈值的慢事件。

### 统计异常是否普遍发生

```bash
rg -nH '{error_keyword_or_field_pattern}' /path/to/service.log | wc -l
```

为什么查这个：判断问题是单次个例还是一段时间内普遍发生。

### 先定位命中文件再展开内容

```bash
timeout 120s bash -c "nice -n 19 rg -l --fixed-strings '{trace_or_keyword}' /path/to/log/root 2>/dev/null"
```

为什么查这个：在不确定具体日志文件时先找文件名，避免一次性输出大量内容。

`rg` 不可用时：

```bash
timeout 120s bash -c "nice -n 19 grep -rIl --binary-files=without-match '{trace_or_keyword}' /path/to/log/root 2>/dev/null"
```

为什么查这个：同上，作为兼容兜底。

### 同时查普通和压缩日志

```bash
rg -nH --fixed-strings '{keyword}' /path/to/*.log
zgrep -nH '{keyword}' /path/to/*.log.*.gz
```

为什么查这个：日志可能已经轮转压缩，单查当前文件会漏上下文。

### 查慢查询或慢依赖关键词

```bash
rg -nH 'slow|cost|duration|elapsed|timeout|took|latency|耗时' /path/to/service.log | rg '{time_prefix_or_window}'
```

为什么查这个：定位性能瓶颈发生在哪个依赖、SQL 或处理阶段。

### 查生命周期或状态覆盖

```bash
rg -nH '{entity_or_resource_id}|{lifecycle_keyword}|{status_keyword}' /path/to/service.log
```

为什么查这个：当数据前后不一致时，定位资源生命周期、状态流转或字段覆盖发生的位置。
