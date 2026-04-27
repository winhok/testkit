# DDL & DML 规范

## Mandatory

- 大表必须设置合理生命周期
- INSERT 必须指定具体字段名：`INSERT INTO t1(f1, f2) VALUES(...)`
  - 禁止 `INSERT INTO t1 VALUES(...)`（字段数量和顺序可能被修改）
- 数据类型不允许全部用 STRING：
  - 数值用 BIGINT/DOUBLE
  - 字符用 STRING
  - 带小数点用 DOUBLE（或金额用厘存 BIGINT），注释说明单位
  - MPP 引擎需要准确数据类型，减少内存消耗

## Preferable

- 建表语句每个字段写 Comment
- 使用 parquet/orcfile + 压缩
- 避免 DROP 语句，需 double check（大表数据不可恢复）
- Impala 引擎 INSERT 后添加统计信息（COMPUTE STATS）
- 非临时表包含分层、主题域、存储策略、存储周期信息

## 建表示例对照

```sql
-- Good
CREATE TABLE dws_user_daily_stats_ds (
    imp_date    BIGINT    COMMENT '时间分区',
    platform    STRING    COMMENT '平台',
    is_vip      BIGINT    COMMENT '0 - 非会员 1 - 会员',
    user_cnt    BIGINT    COMMENT '用户数'
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

-- Bad: 无 comment、字段名不清、无分区、无存储格式
CREATE TABLE t_user_stats (
    date    BIGINT,
    dim1    STRING,
    dim2    BIGINT,
    valOne  BIGINT,
    val2    BIGINT
);
```
