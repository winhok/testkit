# 引擎特性建议

## Spark/Hive

- 关注数据倾斜（key 分布不均导致个别 task 极慢）
- 关注数据膨胀（JOIN/explode 后行数暴增）
- 避免不必要的 UDF/函数调用
- 关注执行计划（DAG stages、Shuffle 数据量）

## Impala

- 避免扫描超大规模数据（Impala 内存模型限制，超出会 OOM）
- JOIN 优化：右表为小表
- 对表和字段做统计信息（COMPUTE STATS）
- 用 parquet 文件格式
- 关注执行计划和 Profile 中的优化提示
- IO 密集型表利用 Alluxio 优化

## ClickHouse

- 选用合适引擎（AggregatingMergeTree/SummingMergeTree 等），减少扫描数据量
- 不用 SELECT *，仅加载需要的列（列式存储特性）
- 避免 JOIN，低于 100w 维度用 Dict 引擎或外部字典表
- 写入路径优先写 Local 表，不直接写 Distributed 表；查询路径按集群路由和诊断目标选择 Distributed 或 Local
- ETL 走 null 表 → Materialized View → local 表
- 选用合理的 ORDER BY key，考虑粒度和查询频率
- 控制写入并发，禁止小 batch 提交
- 建表语句尽量遍历节点执行（关注 ZK 稳定性）
- 关注 ZK 状态和磁盘 IO 负载
- 利用特性函数和类型优化查询

## EXPLAIN 输出引擎识别

| 特征 | 引擎 |
|------|------|
| `type`, `key`, `rows`, `Extra` | MySQL/MariaDB |
| `Seq Scan`, `cost=`, `rows=` | PostgreSQL |
| `ReadType`, `Parts`, `Marks` | ClickHouse |
| `TABLE ACCESS FULL`, `Cost` | Oracle |
| DAG stages, Shuffle | Spark/Hive |
| `SCAN HDFS`, `HASH JOIN` | Impala |
