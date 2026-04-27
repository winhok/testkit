# MySQL 查询性能优化

## EXPLAIN 解读

优化目标：至少 `range`，争取 `ref`，理想 `const`。

| type | 含义 | 行动 |
|------|------|------|
| `system`/`const` | 单行，主键/唯一索引 | 理想 |
| `eq_ref` | JOIN 中每组合一行（PK/唯一索引） | 理想 |
| `ref` | 非唯一索引多行 | 良好 |
| `range` | 索引范围扫描（BETWEEN, >, <, IN） | 可接受 |
| `index` | 全索引扫描 | 需关注 |
| `ALL` | 全表扫描 | 红灯 — 必须加索引 |

Extra 关键信号：
- `Using filesort` — 排序未走索引，需加覆盖 ORDER BY 的索引
- `Using temporary` — 创建临时表，优化 GROUP BY / DISTINCT
- `Using index` — 覆盖索引，仅读索引不回表，最优

## 索引策略

### Mandatory
- 逻辑唯一的字段必须建唯一索引（即使应用层已校验）
- JOIN 两侧字段必须有索引，且数据类型和 collation 一致
- 单表索引不超过 5 个

### 最左前缀原则
组合索引 `(a, b, c)` 可服务 `(a)`、`(a, b)`、`(a, b, c)` 的查询，但不能服务 `(b)`、`(c)`、`(b, c)`。

### 覆盖索引
索引包含查询所需全部列时，MySQL 只读索引不回表（Extra 显示 `Using index`）。这是最强优化之一。

```sql
-- 索引 idx_cover (status, created_at, user_id)
-- 以下查询被覆盖：
SELECT user_id FROM orders WHERE status = 1 AND created_at > '2024-01-01';
```

### 索引失效场景（必须避免）
- 对索引列做函数计算：`WHERE DATE(created_at) = '2024-01-01'` → 改为范围查询
- 隐式类型转换：`WHERE varchar_col = 12345`（无引号）→ 加引号
- 左模糊匹配：`LIKE '%keyword'` → 用全文索引或搜索引擎
- VARCHAR 索引可指定前缀长度，区分度 > 0.9 即可

## JOIN 优化

- JOIN 超过 3 张表需要重点审查执行计划和表规模；高频 OLTP 查询优先拆分或反范式冗余（Preferable）
- 两表 JOIN 必须有索引
- JOIN 两侧数据类型和 collation 必须一致（不一致会隐式转换，索引失效）
- 优先 `INNER JOIN`（优化器自由度更大），不需要未匹配行时不用 `LEFT JOIN`
- 小表驱动大表（MySQL 通常自动优化，用 EXPLAIN 验证）

## 子查询优化

- 优先用 JOIN 替代关联子查询（关联子查询每行执行一次）
- 大结果集用 `EXISTS` 替代 `IN`
- `IN` 配小列表可以，配返回上千行的子查询应改写为 JOIN

## 分页优化

```sql
-- Bad: OFFSET 大时扫描并丢弃大量行
SELECT * FROM t ORDER BY id LIMIT 10 OFFSET 1000000;

-- Good: 游标分页
SELECT * FROM t WHERE id > last_seen_id ORDER BY id LIMIT 10;
```

## 其他陷阱

- `ORDER BY RAND()` 全表扫描 — 用随机 ID 方案替代
- `COUNT(column)` 跳过 NULL — 用 `COUNT(*)` 统计行数
- `= NULL` 永远为 false — 用 `IS NULL` 或 `ISNULL()`
- 禁止在数据库层建外键约束 — 在应用层保证引用完整性
