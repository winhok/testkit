# 审查 SQL 安全、规范与性能

`sql-safety-review` 在执行前评估 SQL 的安全性、结果语义、编码规范和性能风险。它覆盖 MySQL OLTP，以及 Spark/Hive、Impala、ClickHouse 等 OLAP 场景，也能在数据库引擎未知时按通用规则给出保守判断。

## 支持的输入

- `SELECT` 查询。
- `CREATE`、`ALTER` 等 DDL。
- `INSERT`、`UPDATE`、`DELETE` 等 DML。
- MySQL、PostgreSQL、ClickHouse、Spark/Hive 或 Impala 的 `EXPLAIN` 输出。
- 表结构、索引、分区、数据量和预期结果粒度。

只提供 SQL 时也可以开始审查；缺少引擎、表结构或数据规模会作为不确定项，不会被乐观忽略。

## 审查内容

- 扫描范围、分区和索引命中。
- JOIN 输入粒度、唯一性、快照版本和行数放大风险。
- `SELECT *`、无收敛条件、大 OFFSET、隐式转换和前置模糊匹配。
- DDL/DML 的锁、事务、批量修改和回滚风险。
- 命名、大小写、缩进、CASE 完整性和冗余结构。
- 预期输出粒度、唯一键及聚合分子/分母是否一致。

## 结果格式

回答开头先给风险等级和能否执行的结论：

```text
风险等级：高 / 中 / 低
结论：可以直接执行 / 建议先 EXPLAIN / 改写后执行 / 不建议直接执行
```

中高风险结果会列出 Mandatory、Preferable 或 Optional 问题，提供可直接复核的安全改写，并说明需要补充的 `EXPLAIN`、`SHOW CREATE TABLE` 或数量级检查。

典型请求：

```text
这条 MySQL UPDATE 能直接在线上跑吗？
Review 这段 ClickHouse SQL 的结果粒度和性能风险
结合 EXPLAIN 判断这个 JOIN 为什么慢，并给出改写
```

本能力负责审查和改写建议，不因给出“可执行”结论而自动运行 SQL；实际执行仍需要单独授权和目标环境确认。完整规则见 [`sql-safety-review`](../skills/sql-safety-review/SKILL.md)。
