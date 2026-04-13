# TestLib 知识库格式契约

> 目标：定义 `testspec/testlib/` 知识库的目录结构、文件格式和生命周期规则。所有操作 testlib 的 skill 必须遵循本契约。

## 目录结构

```
testspec/testlib/
├── .testlib.json              # 库配置与统计摘要
├── modules/                   # 按模块组织的用例
│   ├── <module-dir>/          # 模块目录
│   │   └── <feature>.json     # 功能用例集（一个文件 = 一个功能的所有用例）
│   └── ...
└── changelog/                 # 发布变更日志
    └── <YYYY-MM-DD>_<change-name>.json
```

### 目录命名规则

| 层级 | 来源 | 转换规则 | 示例 |
|------|------|----------|------|
| 模块目录 | 命名字典 MODULE 缩写 | 大写转小写，`_` 转 `-` | LOGIN → `login/`，USER_AUTH → `user-auth/` |
| 功能文件 | 命名字典 FEATURE 缩写 | 大写转小写，`_` 转 `-`，加 `.json` | CRED → `cred.json`，PHONE_LOGIN → `phone-login.json` |

降级方案（无命名字典）：使用 testcases.json 中 `feature` 字段的拼音或英文 kebab-case。

## 功能用例文件

路径：`testspec/testlib/modules/<module>/<feature>.json`

```json
{
  "schema_version": 1,
  "module": "登录",
  "module_key": "LOGIN",
  "feature": "凭据验证",
  "feature_key": "CRED",
  "last_updated": "2026-04-14",
  "case_count": 5,
  "cases": [
    {
      "id": "user-login_20260414_0001",
      "title": "登录_凭据验证_正确手机号密码登录成功",
      "priority": "P1",
      "type": "冒烟",
      "status": "active",
      "feature": "登录",
      "preconditions": "1、用户已完成手机号注册",
      "steps": "1、打开 App 首页\n2、点击登录按钮\n3、输入已注册手机号和正确密码\n4、点击确认",
      "expected_result": "1、跳转至首页\n2、顶部显示用户名",
      "tp_refs": ["TP_LOGIN_CRED_001"],
      "tags": [],
      "source_change": "user-login",
      "created_at": "2026-04-14",
      "updated_at": "2026-04-14"
    }
  ]
}
```

### 文件级字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| schema_version | number | ★ | 固定 `1`，后续升级时递增 |
| module | string | ★ | 中文模块名，与 testpoints.md `### {模块}模块` 一致 |
| module_key | string | ★ | 命名字典 MODULE 缩写（A-Z，2-5 字符） |
| feature | string | ★ | 中文功能名，与 testpoints.md `#### {功能}功能` 一致 |
| feature_key | string | ★ | 命名字典 FEATURE 缩写（A-Z，2-10 字符） |
| last_updated | string | ★ | ISO 日期 YYYY-MM-DD，每次 publish 时更新 |
| case_count | number | ★ | cases 数组实际长度，publish 时自动计算 |
| cases | array | ★ | 用例数组，至少 1 个元素 |

### 用例级字段

| 字段 | 类型 | 必填 | 说明 | 来源 |
|------|------|------|------|------|
| id | string | ★ | 全局唯一 ID | testcases.json `id` 直接映射 |
| title | string | ★ | 三段式标题 `{模块}_{功能}_{场景}` | testcases.json `title` |
| priority | string | ★ | P1 / P2 / P3 | testcases.json `priority` |
| type | string | ★ | 冒烟/正向/负向/边界/异常/其他 | testcases.json `type` |
| status | string | ★ | 生命周期状态（见下方） | publish 时设置 |
| feature | string | ★ | 模块名（= 文件级 module） | testcases.json `feature` |
| preconditions | string | | 编号前置条件 `1、xxx\n2、xxx` | testcases.json `preconditions` |
| steps | string | ★ | 编号操作步骤 | testcases.json `steps` |
| expected_result | string | ★ | 编号预期结果 | testcases.json `expected_result` |
| tp_refs | string[] | | 关联 TP_ID 列表 | testcases.json `tp_refs` |
| tags | string[] | | 用例级标签 | publish 时可附加 |
| source_change | string | ★ | 来源变更目录名 | 从 `changes/<name>` 提取 |
| created_at | string | ★ | 首次入库日期 YYYY-MM-DD | 新入库 = 当天 |
| updated_at | string | ★ | 最后更新日期 YYYY-MM-DD | 每次 publish = 当天 |

### 状态生命周期

```
active ──→ deprecated ──→ archived
  ↑            │
  └────────────┘（可回退）
```

| 状态 | 含义 | 何时进入 |
|------|------|----------|
| active | 有效，参与回归测试 | 新入库 / 被更新后 |
| deprecated | 已过期，保留供参考 | 功能下线或需求变更导致用例失效 |
| archived | 归档，不再显示于统计 | deprecated 超过一个季度 |

新入库的用例始终为 `active`。更新已有用例时保留原 status（除非用户显式要求变更）。

## 变更日志

路径：`testspec/testlib/changelog/<YYYY-MM-DD>_<change-name>.json`

```json
{
  "change_name": "user-login",
  "date": "2026-04-14",
  "source_dir": "testspec/changes/user-login",
  "summary": "用户登录功能测试用例入库",
  "operations": {
    "added": ["user-login_20260414_0001", "user-login_20260414_0002"],
    "updated": [],
    "deprecated": [],
    "unchanged": 0
  },
  "affected_modules": ["login"],
  "_context": {
    "source_skill": "testspec-publish",
    "source_change": "user-login"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| change_name | string | ★ | 变更名 |
| date | string | ★ | 发布日期 YYYY-MM-DD |
| source_dir | string | ★ | 来源变更目录相对路径 |
| summary | string | ★ | 一句话描述本次发布内容 |
| operations.added | string[] | ★ | 新增用例 ID 列表 |
| operations.updated | string[] | ★ | 更新用例 ID 列表 |
| operations.deprecated | string[] | ★ | 废弃用例 ID 列表 |
| operations.unchanged | number | ★ | 未变更的已有用例数 |
| affected_modules | string[] | ★ | 涉及的模块目录名列表 |
| _context | object | | 上下文元数据（按 context-protocol.md） |

## 库配置

路径：`testspec/testlib/.testlib.json`

```json
{
  "schema_version": 1,
  "created_at": "2026-04-14",
  "last_updated": "2026-04-14",
  "stats": {
    "total_modules": 2,
    "total_features": 5,
    "total_cases": 23,
    "by_status": {
      "active": 20,
      "deprecated": 3,
      "archived": 0
    },
    "by_priority": {
      "P1": 8,
      "P2": 10,
      "P3": 5
    }
  }
}
```

stats 由 testspec-publish 在每次发布后扫描 `modules/` 全量重算。

## 与 testcases.json 的兼容性

### v2 格式

testcases.json v2 的所有字段直接映射到 testlib，无需转换。publish 时额外添加生命周期字段（status、source_change、created_at、updated_at、tags）。

### v1 兼容

testcases.json v1（扁平数组）同样支持。publish skill 自动检测：
- 顶层为数组 → v1
- 顶层为对象且含 `schema_version` → v2

v1 缺少 `tp_refs` 字段时，testlib 中 `tp_refs` 设为空数组。

## 变更控制

以下修改属于高风险变更，需同步更新 testspec-publish 和所有消费方：

- `schema_version` 升级
- 必填字段增减
- 目录命名规则变更
- 状态枚举值变更
- 变更日志字段变更
