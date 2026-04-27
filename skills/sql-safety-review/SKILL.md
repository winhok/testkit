---
name: sql-safety-review
description: 评估 SQL 查询的安全性、规范性和性能风险。覆盖 OLAP（Spark/Hive、Impala、ClickHouse）和 OLTP（MySQL）两大场景。审查维度：命名规范、编码格式、查询优化、索引策略、DDL/DML 规范、引擎特性、锁与事务。当用户贴出 SQL 问"能不能跑"、"会不会查爆"、"帮我 review"、"格式对不对"、"命名规范吗"、"这个 EXPLAIN 怎么看"、"为什么这么慢"、"能不能在生产跑"、"帮我看看这条 SQL"、"这个查询有没有问题"、"Code Review 一下"、"建表语句有问题吗"、"ETL 上线前审查"、"慢查询优化"、"索引怎么建"、"会不会死锁"、"大批量删除怎么做"时触发。即使用户只是贴了一条 SQL 没说别的，也应触发。支持 SELECT/DDL/DML/EXPLAIN 输出分析。
---

# SQL Safety & Standards Review

IRON LAW: 输出开头必须先给风险等级和结论。禁止先分析再给结论。

## 核心原则

1. **结论先行** — 开头两行给风险等级 + 能不能跑，再展开
2. **默认保守** — 缺少表结构/数据量信息时，按中高风险处理
3. **风险 + 规范一起审** — 不分两次，一次性给出完整评估
4. **规范约束分级** — 区分必须(Mandatory)、推荐(Preferable)、可选(Optional)
5. **精简有力** — 每条风险一两句话说清，不写教程
6. **引擎感知** — 根据用户声明或 SQL 特征自动选择对应引擎的规范

## 适用范围

| 场景 | 引擎 | 规范参考 |
|------|------|----------|
| OLAP 数据仓库 | Spark/Hive、Impala、ClickHouse | references/naming-standards.md, coding-format.md, query-performance.md, ddl-dml-standards.md, engine-specific.md |
| OLTP 业务系统 | MySQL | references/mysql-naming.md, mysql-query-performance.md, mysql-ddl-dml.md, mysql-engine.md |
| 通用 SQL | 未知引擎 | 使用通用规则，提示用户确认引擎 |

## 审查工作流

```
- [ ] Step 1: 识别输入类型和查询目标
- [ ] Step 2: 静态风险扫描（安全 + 规范）
- [ ] Step 3: 给出风险等级和结论 ⚠️ REQUIRED — 必须在输出开头
- [ ] Step 4: 改写建议（中高风险时）
- [ ] Step 5: 引导补充信息（需要时）
- [ ] Step 6: 精确分析（有 EXPLAIN/表结构时）
```

### Step 1 — 识别输入类型、引擎和查询目标

**1a. 判断引擎**

从以下线索识别引擎（优先级从高到低）：
1. 用户明确声明（"我们用 MySQL"、"ClickHouse 上跑的"）
2. SQL 语法特征（`ENGINE=InnoDB` → MySQL、`PARTITIONED BY` → Hive、`ORDER BY key` in CREATE → ClickHouse）
3. EXPLAIN 输出格式（见 references/engine-specific.md 引擎识别表）
4. 无法判断 → 标注"引擎未知"，使用通用规则，提示用户确认

引擎确定后加载对应规范：
- OLAP（Spark/Hive、Impala、ClickHouse）→ references/naming-standards.md, query-performance.md, ddl-dml-standards.md, engine-specific.md
- MySQL → references/mysql-naming.md, mysql-query-performance.md, mysql-ddl-dml.md, mysql-engine.md
- 通用 → references/coding-format.md + 通用规则

**1b. 判断输入类型**

| 输入类型 | 处理方式 |
|---------|----------|
| SELECT 查询 | 完整安全 + 规范审查 |
| DDL（CREATE/ALTER） | 命名规范 + DDL 规范审查 → 加载对应引擎的 ddl-dml 参考 |
| DML（INSERT/UPDATE/DELETE） | DML 规范 + 安全审查 → 加载对应引擎的 ddl-dml 参考 |
| EXPLAIN 输出 | 直接进入 Step 6 精确分析 → 加载对应引擎参考 |
| 纯文字描述 | 引导用户贴出 SQL 或 EXPLAIN |

推断查询目标：

| 用户目标 | 安全做法 |
|---------|----------|
| 确认"有没有数据" | `SELECT 1 ... LIMIT 1` 或 `COUNT(*)` |
| 确认数量级 | `COUNT(*)` + 合理过滤 |
| 抽样看几条 | 关键字段 + `LIMIT` |
| 查完整明细 | 强过滤 + 分页 |
| 定位慢查询 | 先 EXPLAIN |
| 判断能否线上跑 | 完整风险评估 |

如果用户没说目标，从 SQL 结构推断并在输出中说明推断依据。

### Step 2 — 静态风险扫描

逐项检查以下风险信号。对每条命中的规则，标注级别（Mandatory/Preferable）。

**扫描范围风险**
- 无 WHERE / 条件过宽
- 明确为分区表或 OLAP 大表时缺少分区字段
- 数据量大但缺少收敛条件

**索引/分区命中风险**
- 过滤条件未命中分区列（OLAP）或索引列（MySQL）
- 对列做函数计算（如 `DATE(created_at)`）— 索引失效
- 隐式类型转换（如 `WHERE varchar_col = 12345` 无引号）— 索引失效
- 前置模糊匹配（`LIKE '%xxx'`）— 索引失效
- OR / NOT IN / != 等不利条件

**JOIN 风险**
- 多表 JOIN 关联条件不明确 / 驱动表行数过大
- 大表 JOIN 前未先过滤（应在子查询中先过滤再 JOIN）— Preferable，规模很大时升级为 Mandatory
- 笛卡尔积 — Mandatory 违规
- MySQL: JOIN 超过 3 张表 — Preferable 风险提示，需结合 EXPLAIN 和表规模确认
- MySQL: JOIN 两侧数据类型或 collation 不一致 — 索引失效

**结果集风险**
- SELECT * — Mandatory 违规
- 无 LIMIT / 结果集可能很大
- MySQL: 大 OFFSET 分页（`LIMIT 10 OFFSET 1000000`）— 应改游标分页

**格式与命名规范** — 加载对应引擎的命名规范参考按需检查：
- 关键字大小写混用 — Mandatory 违规
- 命名不符合规范（驼峰、保留字、缩写不清）
- 缩进混乱、单行过长
- CASE WHEN 缺少 ELSE 子句

### Step 3 — 给出风险等级 ⚠️ REQUIRED

这是输出开头，格式固定：

```
## 风险等级：高/中/低

**结论：** [一句话说清能不能跑、怎么跑]
```

判定标准：
- **低风险** — 明确命中主键/唯一键或强过滤、扫描范围小、有 LIMIT、格式规范
- **中风险** — 有 WHERE 但索引/分区命中不确定、有 JOIN 但规模可控
- **高风险** — 无 WHERE / 无分区 / 全表扫描 / 多表大 JOIN / SELECT *

最终建议必须是以下之一：
- ✅ 可以直接执行
- ⚠️ 建议先 EXPLAIN 确认
- 🔧 建议加条件/改写后执行
- 🚫 不建议直接执行，给出替代方案

### Step 4 — 改写建议（中高风险时）

**缩范围**：加分区条件（OLAP）或索引条件（MySQL）、加业务主键、加时间范围
**缩结果**：SELECT 具体字段、加 LIMIT、先 COUNT 确认量级；MySQL 大分页改游标分页
**降复杂度**：去不必要 ORDER BY、拆分大查询、大表先过滤再 JOIN、OLAP 大表小表用 map join、MySQL 用覆盖索引
**修格式**：统一关键字大小写、修正命名、调整缩进对齐、补 ELSE 子句
**MySQL 特有**：批量 UPDATE/DELETE 按主键分段、大批量删除用换表模式或 DROP PARTITION、INSERT 指定字段名

改写 SQL 必须遵循编码格式规范（references/coding-format.md）和命名规范（references/naming-standards.md）。

### Step 5 — 引导补充信息

缺少信息时，给出可直接复制的命令：
- `EXPLAIN SELECT ...;`
- `SHOW CREATE TABLE table_name;`
- `SELECT COUNT(*) FROM table_name WHERE 分区条件;`

### Step 6 — 精确分析（有 EXPLAIN/表结构时）

根据 EXPLAIN 输出特征自动识别引擎：
- `type`, `key`, `rows`, `Extra` → MySQL → 加载 references/mysql-query-performance.md, mysql-engine.md
- `Seq Scan`, `cost=`, `rows=` → PostgreSQL（仅做通用执行计划判断，提示用户补充数据库版本和索引信息）
- `ReadType`, `Parts`, `Marks` → ClickHouse → 加载 references/engine-specific.md
- DAG stages, Shuffle → Spark/Hive → 加载 references/engine-specific.md
- `SCAN HDFS`, `HASH JOIN` → Impala → 加载 references/engine-specific.md

结合 EXPLAIN 和表结构更新风险等级，给出确定性结论和引擎特性建议。

## 输出格式

**低风险**：风险等级 + 结论 + 一句话原因 + 小优化点（如有）

**中高风险完整输出：**
1. **风险等级 + 结论**（输出开头，固定格式）
2. **查询目标推断**
3. **风险原因**（逐条，每条一两句，标注 Mandatory/Preferable 级别）
4. **规范问题**（命名/格式/结构，如有）
5. **更安全的写法**（可直接使用的改写 SQL）
6. **下一步操作**（EXPLAIN 等命令）

## 反模式清单

审查时禁止出现以下行为：

- 先写一大段分析再给结论（违反 Iron Law）
- 只审安全不审规范，或只审规范不审安全（必须一次性完成）
- 给出模糊建议如"建议优化一下"而不给具体改写 SQL
- 改写 SQL 本身不符合编码格式规范（如混用大小写、无缩进）
- 对低风险查询过度分析（低风险 = 简短回复）
- 缺少信息时乐观假设（必须默认保守）
- 不标注规则级别（每条问题必须标注 Mandatory/Preferable/Optional）
- 引擎特性建议在不确定引擎时给出（只在明确知道引擎时才给）

## Code Review 场景

以下场景必须进行 Code Review：
- ETL JOB 上线
- DDL & DML 语句
- 收到系统推送的慢查询和优化提示

Code Review 关注：代码逻辑准确性、代码风格、效率、注释充分性、数仓规范符合度。

## 回答风格

- 结论先行，不绕弯
- 风险 + 规范一起审，不分两次
- 给落地的改写 SQL，不空谈理论
- 缺少信息时保守判断，标注不确定点
- 引擎特性建议只在明确知道引擎时给出
- 改写 SQL 中的命名须符合命名规范
