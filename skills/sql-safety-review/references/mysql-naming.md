# MySQL 命名规范

## 数据库命名（Mandatory）

- 全小写 `snake_case`，≤30 字符
- 格式：`{业务线}_{服务名}_db`（如 `trade_order_db`）
- 禁止中文、拼音、拼音英文混用

## 表命名（Mandatory）

- 全小写 `snake_case`，单数形式（`order_detail` 而非 `order_details`）
- 格式：`{业务名}_{表用途}`（如 `alipay_task`、`trade_config`）
- 禁止使用 MySQL 保留字（`order`、`group`、`key`、`range`、`match`、`desc`、`status`）
- 每张表必须有 COMMENT 说明用途
- 每张表必须包含三个字段：`id`、`created_at`、`updated_at`

## 字段命名（Mandatory）

- 全小写 `snake_case`，不以数字开头
- 布尔字段：`is_xxx` + `TINYINT UNSIGNED`（1=true, 0=false）
- 外键字段：`{被引用表}_id`（如 `customer_id`）
- 每个字段必须有 COMMENT

## 标准后缀约定

| 后缀 | 含义 | 示例 |
|------|------|------|
| `_id` | 唯一标识 | `user_id` |
| `_at` / `_time` | 时间 | `created_at`, `pay_time` |
| `_status` | 状态 | `review_status`, `pay_status` |
| `_amount` / `_price` | 金额 | `order_amount`, `sale_price` |
| `_count` / `_cnt` | 计数 | `retry_count` |
| `_by` / `_user` | 操作人 | `updated_by`, `create_user` |
| `_name` | 名称 | `product_name` |

## 索引命名（Mandatory）

| 类型 | 前缀 | 示例 |
|------|------|------|
| 主键 | `pk_` | `pk_id` |
| 唯一索引 | `uk_` | `uk_email` |
| 普通索引 | `idx_` | `idx_user_id` |
| 组合索引 | `idx_` | `idx_status_created_at`（按最左前缀顺序） |
| 全文索引 | `ft_` | `ft_content` |

索引名不超过 50 字符。

## 反例速查

```sql
-- Bad: 保留字、驼峰、无 comment
CREATE TABLE order (
    orderNo VARCHAR(64),
    userId BIGINT,
    Status TINYINT
);

-- Good: 规范命名、有 comment、有标准字段
CREATE TABLE order_detail (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_no    VARCHAR(64)     NOT NULL DEFAULT '' COMMENT '订单号',
    user_id     BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '用户ID',
    status      TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '状态: 0=待处理, 1=已支付',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='订单明细';
```
