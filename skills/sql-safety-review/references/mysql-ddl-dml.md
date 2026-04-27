# MySQL DDL & DML 规范

## CREATE TABLE 标准模板

```sql
CREATE TABLE order_detail (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id     BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
    order_no    VARCHAR(64)     NOT NULL DEFAULT '' COMMENT '订单号',
    amount      DECIMAL(10,2)   NOT NULL DEFAULT 0.00 COMMENT '订单金额',
    status      TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态: 0=待处理, 1=已支付, 2=已发货',
    is_deleted  TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '软删除: 0=否, 1=是',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_user_id (user_id),
    KEY idx_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='订单明细';
```

## DDL 规则

### Mandatory
- 主键：`BIGINT UNSIGNED AUTO_INCREMENT`（不用 INT，预留空间）
- 所有字段 `NOT NULL` + 合理默认值（NULL 复杂化查询、浪费索引空间）
- 非负字段用 `UNSIGNED`（ID、计数、状态码）
- 金额用 `DECIMAL` — 禁止 `FLOAT`/`DOUBLE`
- `VARCHAR(N)` 按实际最大长度选 N，不盲目用 `VARCHAR(255)`；超过 5000 用 `TEXT` 并拆表
- 必须指定 `ENGINE=InnoDB`、`CHARSET=utf8mb4`
- 禁止用 `utf8`（即 `utf8mb3`，只支持 3 字节，不能存 emoji）
- 禁止用 `ENUM` — 改值需 ALTER TABLE，用 `TINYINT` + 应用层映射
- 主键用自增 BIGINT — 随机 UUID 做主键会导致页分裂和碎片化

### Preferable
- MySQL 8.0+: collation 用 `utf8mb4_0900_ai_ci`
- MySQL 5.7: collation 用 `utf8mb4_unicode_ci`
- 每个字段和表都写 COMMENT
- 大表（百万+行）考虑分区（RANGE 按日期最常见）

## ALTER TABLE（Online DDL）

MySQL 8.0 三种算法：
| 算法 | 说明 | 适用 |
|------|------|------|
| `INSTANT` | 仅改元数据，最快 | 末尾加列、加/删虚拟列 |
| `INPLACE` | 原地重建，允许并发 DML | 大部分索引操作、列重命名 |
| `COPY` | 全表复制，阻塞写入 | 改列类型、转字符集 |

大表（百万+行）需要 COPY 算法时，用 `pt-online-schema-change` 或 `gh-ost`。

验证方式：
```sql
ALTER TABLE t ADD COLUMN new_col INT, ALGORITHM=INPLACE, LOCK=NONE;
-- 不支持 INPLACE 时会报错而非静默降级为 COPY
```

## INSERT 规范

- 批量插入用多行语法，每批 500–5000 行（不超过 `max_allowed_packet`）
- 包在显式事务中减少提交开销
- 大规模初始加载用 `LOAD DATA INFILE`
- `INSERT ... ON DUPLICATE KEY UPDATE` 会获取 next-key lock，高并发下可能死锁

## UPDATE 规范

- WHERE 必须命中索引，否则可能锁全表
- 大批量更新按主键分段：
```sql
UPDATE orders SET status = 2
WHERE status = 1 AND id BETWEEN 1 AND 10000;
-- 然后 10001-20000，依此类推
```
- 保持事务短小 — 长事务持锁阻塞其他操作

## DELETE 规范

- 禁止单条语句删除百万行（巨大 undo log + 持锁 + 阻塞复制）
- 分批删除 + LIMIT：
```sql
DELETE FROM logs WHERE created_at < '2023-01-01' LIMIT 10000;
-- 循环直到影响行数为 0，批次间短暂暂停让从库追上
```
- 删除大部分数据时用"换表"模式：
```sql
CREATE TABLE t_new LIKE t_old;
INSERT INTO t_new SELECT * FROM t_old WHERE <保留条件>;
RENAME TABLE t_old TO t_backup, t_new TO t_old;
```
- 分区表用 `ALTER TABLE t DROP PARTITION p2023`（近乎瞬时）
