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
| JOIN 粒度与唯一性 | 声明左右输入粒度、关联键唯一性和预期输出粒度；相对于预期粒度不满足时先预聚合或按业务规则去重 | Mandatory |
| 时态数据对齐 | 快照/拉链/分区维表按业务日期、版本或有效期关联，禁止只按实体 ID 挂接多个历史版本 | Mandatory |
| 外连接谓词位置 | 根据保留未匹配行的语义选择 ON、输入子查询或 WHERE；不得把右表过滤机械移入 WHERE | Mandatory |
| 大表 JOIN 小表用 map join | 使用 SQL hint: `/*mapjoin(小表别名)*/` | Preferable |
| 先 WHERE 再 JOIN | 大表 JOIN 前在子查询中先过滤，减少处理数据量；小表场景结合执行计划判断 | Preferable |
| 减少多层 JOIN | 考虑冗余重要信息到宽表 | Preferable |
| 删除透传层 | 子查询/CTE 若不裁剪数据、不改变粒度、也不隔离必要复杂逻辑，应合并或删除 | Preferable |
| 去掉不必要的 IS NOT NULL | 换成 `>=` 或 `<=` | Optional |
| 多重判断用 CASE | 替代多个 IF/OR 嵌套 | Preferable |
| OR 条件转 UNION ALL | WHERE 中仅有 OR 时可改写 | Optional |

## JOIN 结果正确性

有 `ON` 条件只能排除笛卡尔积，不能证明结果粒度正确。审查 JOIN 时：

1. 写出左右输入各自“一行代表什么”。
2. 确认关联键在应唯一的一侧是否真的唯一；未知时要求唯一约束、表结构或重复计数证据。
3. 写出 JOIN 后预期“一行代表什么”。
4. 一对多是业务所需时，检查下游聚合是否会重复累计左表指标；不是业务所需时，在 JOIN 前预聚合或按明确规则去重。
5. 对比 JOIN 前后行数、主键去重数和核心金额/计数总量，不能只看 SQL 是否执行成功。

快照表、拉链表和按日分区维表还必须对齐事实发生时间：

```sql
-- Bad: 同一用户的多个快照都可能命中
ON fact.user_id = profile.user_id

-- Good: 示例为按日快照；实际项目也可使用版本号或有效期区间
ON fact.user_id = profile.user_id
AND fact.stat_date = profile.snapshot_date
```

## 外连接过滤语义

不要照搬“ON 只写关联键、过滤全部放 WHERE”。对于 `LEFT JOIN`：

- 右表过滤写入 `WHERE` 会删除未匹配行，常等价于把外连接改成内连接。
- 需要保留左表未匹配行时，在右表输入子查询/CTE 中预过滤，或把限定条件留在 `ON`。
- 确实只保留匹配行时，优先明确写 `INNER JOIN`，避免依赖隐式语义。

## CASE 分桶验数

审查区间、等级或枚举分桶时，检查边界空洞、重叠和 NULL。临时验数可以让 `ELSE`
携带未命中的原始值，或单独输出异常明细：

```sql
-- Hive/Spark 示例；其他引擎使用对应的文本类型和转换函数
CASE
    WHEN score >= 0 AND score < 60 THEN 'low'
    WHEN score >= 60 THEN 'high'
    ELSE CONCAT('__unmatched__:', COALESCE(CAST(score AS STRING), 'null'))
END
```

该写法只能用于临时诊断。正式落表、稳定报表或作为下游分组键时，必须恢复为稳定枚举，
并通过独立异常查询或质量指标保留可观测性，避免高基数碎片污染结果。

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
