# 编码格式规范

## Mandatory

- 关键字必须全大写或全小写，禁止混用（`seleCT ... group BY` 是典型违规）
- 每行不超过 80 字符，禁止所有代码堆在一两行
- 使用空格缩进（4 空格 = 1 缩进量），禁止 TAB
- SELECT/FROM/WHERE/GROUP BY/ORDER BY/JOIN/UNION 等子句左对齐，子句内容缩进 1 级
- 等号前后、逗号后必须有空格
- 禁止 `SELECT *`，明确列出所需字段
- 大表多表关联时优先在子查询中先过滤再 JOIN；小表或优化器可下推时结合执行计划判断
- CASE WHEN：WHEN 缩进 1 级，必须包含 ELSE，END 与 CASE 对齐
- 子查询及 WITH 子句，左右括号必须列对齐

## Preferable

- 单语句不超过 100 行，过长用 WITH 拆分
- 嵌套子查询前添加注释说明作用和主键
- 硬编码常量和 `${date}` `${hour}` 加减操作必须注释
- AND/OR 前换行
- 逗号写在字段前面（避免遗漏，方便批量编辑）

## 标准格式示例

```sql
SELECT
    imp_date
    , platform
    , is_vip
    , COUNT(DISTINCT qimei) AS user_cnt
FROM
    tb_db.table
WHERE
    imp_date >= 20210506
    AND imp_date <= 20210511
GROUP BY
    imp_date
    , platform
    , is_vip
```

## CASE WHEN 示例

```sql
SELECT
    imp_date
    , CASE
          WHEN channel = '1' THEN 'App Store'
          WHEN channel = '2' THEN 'Google Play'
          WHEN channel = '3' THEN 'xxxx'
          ELSE channel
      END AS channel_name
    , COUNT(DISTINCT user_id) AS user_cnt
FROM
    tb_db.table
WHERE
    imp_date >= 20210506
    AND imp_date <= 20210511
GROUP BY
    imp_date
    , channel_name
```

## 典型违规对照

```sql
-- Bad: 混用大小写、无换行、无缩进
seleCT imp_date,platform,is_vip,COUNT(distinct qimei) AS user_cnt from tb_db.table where
imp_date >= 20210506 and imp_date <= 20210511 group BY imp_date ,platform,is_vip

-- Bad: 首字母大写
Select imp_date,platform
,is_vip,count(distinct qimei) as usercnt
From tb_db.table
Where imp_date >= 20210506
and imp_date <= 20210511
Group By imp_date ,platform,is_vip
```
