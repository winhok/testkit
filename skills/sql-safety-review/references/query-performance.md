# 查询性能规范

## Mandatory

- 明确为分区表或 OLAP 大表时，查询必须加分区字段（时间分区等），避免全表扫描
- 明细查询必须加 LIMIT
- 禁止在子查询中 SELECT *，去掉不必要的列

## 性能优化规则表

| 规则 | 说明 | 级别 |
|------|------|------|
| 分区过滤 | 明确为分区表或 OLAP 大表时必须包含分区字段条件，避免万亿级大表全局扫描 | Mandatory |
| EXPLAIN 先行 | 不熟悉的表先看执行计划，评估资源消耗 | Preferable |
| 查上层表 | 优先查聚合表而非明细表，减少 IO | Preferable |
| WHERE 避免函数 | 不对列做函数转换或强制类型转换 | Preferable |
| 避免 LIKE 前缀模糊 | `LIKE '%xxx'` 无法走索引，用 IN 替代 | Preferable |
| 用 IN 替代多 OR | 提高可读性和优化器效率 | Preferable |
| 用 UNION ALL 替代 UNION | 无重复时避免去重开销 | Preferable |
| 避免笛卡尔积 | JOIN 必须有明确关联条件 | Mandatory |
| 大表 JOIN 小表用 map join | 使用 SQL hint: `/*mapjoin(小表别名)*/` | Preferable |
| 先 WHERE 再 JOIN | 大表 JOIN 前在子查询中先过滤，减少处理数据量；小表场景结合执行计划判断 | Preferable |
| 减少多层 JOIN | 考虑冗余重要信息到宽表 | Preferable |
| 去掉不必要的 IS NOT NULL | 换成 `>=` 或 `<=` | Optional |
| 多重判断用 CASE | 替代多个 IF/OR 嵌套 | Preferable |
| OR 条件转 UNION ALL | WHERE 中仅有 OR 时可改写 | Optional |

## map join 示例

```sql
SELECT /*mapjoin(t2)*/
    imp_date
    , channel_type_1
    , channel_type_2
    , SUM(new_user) AS new_user
FROM
(
    SELECT
        imp_date
        , channel_id
        , COUNT(user_id) AS new_user
    FROM
        tb_db.table
    WHERE
        imp_date = 20210506
        AND is_new_user = 1
    GROUP BY
        imp_date
        , channel_id
) t1
LEFT JOIN
(
    SELECT
        channel_id
        , channel_type_1
        , channel_type_2
    FROM
        tb_db.dim_table
    WHERE
        imp_date = 20210506
) t2
ON
    t1.channel_id = t2.channel_id
GROUP BY
    imp_date
    , channel_type_1
    , channel_type_2
```
