# MySQL 引擎特性

## InnoDB 核心要点

- InnoDB 是唯一生产级引擎，必须 `ENGINE=InnoDB`
- Buffer Pool：独立 MySQL 服务器设为可用内存的 60–80%（最重要的调优参数）
- `innodb_flush_log_at_trx_commit = 1` 保证 ACID；设为 `2` 仅在可容忍 1 秒数据丢失时
- 主键设计：InnoDB 按主键聚簇存储，自增 BIGINT 最优；随机 UUID 做主键导致页分裂

## 锁行为

- 默认 `REPEATABLE READ` 隔离级别，使用 next-key lock（记录锁 + 间隙锁）
- 间隙锁防止幻读，但高并发 INSERT/UPDATE 场景可能死锁
- 缓解策略：
  - 切换到 `READ COMMITTED`（消除大部分间隙锁，阿里等大厂生产环境常用）
  - 保持事务尽量短
  - 所有事务按一致顺序访问表/行
  - 加合适索引减少锁定行数
  - 应用层设计死锁重试逻辑
- `SHOW ENGINE INNODB STATUS\G` 查看 `LATEST DETECTED DEADLOCK`
- `SELECT ... FOR UPDATE` 和 `SELECT ... LOCK IN SHARE MODE` 显式加锁 — 谨慎使用

## 字符集与 Collation

- 必须用 `utf8mb4`（MySQL 的 `utf8` 即 `utf8mb3` 只支持 3 字节，不能存 emoji，已废弃）
- MySQL 8.0+: `utf8mb4_0900_ai_ci`
- MySQL 5.7: `utf8mb4_unicode_ci`
- JOIN 两侧 collation 不一致时索引失效 — 常见隐性性能杀手

## 分区

- 超大表（1 亿+ 行）且查询天然按分区键过滤时使用
- 常见策略：`RANGE` 按日期（月分区用于日志/事件表）、`HASH` 均匀分布
- `DROP PARTITION` 近乎瞬时（vs 逐行删除）
- 陷阱：
  - WHERE 不含分区键 → 扫描所有分区（比不分区更差）
  - 唯一索引必须包含分区键
  - 小表不要分区（开销不值得）
