# 命名规范

## 通用规则（Mandatory）

- 只用字母、数字、下划线；以字母开头，不以下划线结尾
- 不允许连续下划线、驼峰命名、保留关键字
- 库名全小写 ≤30 字符
- 表名全小写 ≤50 字符，符合分层规范（dim/ods/dws/dwd/ads/dm）
- 字段名全小写 ≤32 字符
- 布尔列命名为 `is_描述`（如 `is_enabled`）

## 推荐规则（Preferable）

- 用贴切英文单词，避免拼音；缩写须简明易懂
- 各表相同含义字段应同名且同类型
- 字段加注释，枚举型注明含义（如 `0 - 离线，1 - 在线`）
- 避免 uid/pid/cid 等模糊缩写
- 表名用单数形式（employee 而非 employees）
- 表名不能和列名同名

## 标准后缀约定（Optional）

| 后缀 | 含义 | 示例 |
|------|------|------|
| `_cnt` | 数值统计 | `user_cnt` |
| `_uv` | 去重计数 | `play_uv` |
| `_amt` | 金额 | `charge_amt` |
| `_ts` | 时间长度 | `play_ts` |
| `_rate` | 比例 | `click_rate` |
| `_id` | 唯一标识 | `user_id` |
| `_name` | 名称 | `task_name` |
| `_status` | 状态值 | `query_status` |
| `_date` | 日期 | `stat_date` |
| `_hour` | 小时 | `stat_hour` |
| `_area` | 面积 | `exp_area` |

## 反例速查

```sql
-- Bad: 驼峰、下划线开头/结尾、缩写不清、保留字
_uid, mid_, mediaId, valOne, val2, date, option, order

-- Good: 清晰、下划线分割、语义明确
user_id, media_id, user_cnt, stat_date, query_option, imp_date
```

### 库命名

```
-- Good: kiti_user_ods, kiti_live_dm, kiti_game_ads
-- Bad:  user, live, game
```

### 表命名

```
-- Good: dim_newsapp_channel_basic_info_d_f, ods_app_startup_noadd_di
-- Bad:  t_newsapp_bi_install_channel_basic_info_accum
```
