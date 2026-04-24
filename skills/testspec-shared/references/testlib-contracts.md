# TestLib 知识库格式契约

> 目标：定义 `testspec/testlib/` 知识库的目录结构、文件格式和生命周期规则。所有操作 testlib 的 skill 必须遵循本契约。

## 设计原则

借鉴 wiki 知识库模式，testlib 不仅是用例仓库，更是可检索、互联的测试知识网络：

- **一文件一实体**：每个 `<feature>.json` 对应一个功能点的所有用例，是知识库的最小单元
- **交叉引用**：功能间通过 `related_features` 建立关联（如"登录"与"注册"互为关联）
- **全局索引**：`index.json` 提供扁平化的模块/功能/用例目录，支持快速检索
- **操作日志**：`log.md` 顶部插入每次入库记录（最新在前），人可读、可追溯
- **增量更新**：每次 publish 只变更受影响的文件，同时维护索引和交叉引用的一致性

## 目录结构

```
testspec/testlib/
├── .testlib.json              # 库配置与统计摘要
├── index.json                 # 全局索引（模块→功能→用例摘要）
├── log.md                     # 操作日志（顶部插入，最新在前）
├── modules/                   # 按模块组织的用例
│   ├── <module-dir>/          # 模块目录
│   │   └── <feature>.json     # 功能用例集（一个文件 = 一个功能的所有用例）
│   └── ...
└── changelog/                 # 发布变更日志（结构化 JSON）
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
  "schema_version": 2,
  "module": "登录",
  "module_key": "LOGIN",
  "feature": "凭据验证",
  "feature_key": "CRED",
  "last_updated": "2026-04-14",
  "case_count": 5,
  "related_features": [
    { "path": "login/phone-login", "relation": "同模块" },
    { "path": "register/basic", "relation": "前置依赖", "note": "用户需先注册才能登录" }
  ],
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
| schema_version | number | ★ | 固定 `2`，后续升级时递增 |
| module | string | ★ | 中文模块名，与 testpoints.md `### {模块}模块` 一致 |
| module_key | string | ★ | 命名字典 MODULE 缩写（A-Z，2-5 字符） |
| feature | string | ★ | 中文功能名，与 testpoints.md `#### {功能}功能` 一致 |
| feature_key | string | ★ | 命名字典 FEATURE 缩写（A-Z，2-10 字符） |
| last_updated | string | ★ | ISO 日期 YYYY-MM-DD，每次 publish 时更新 |
| case_count | number | ★ | cases 数组实际长度，publish 时自动计算 |

> **元数据稳定性**：`module`/`module_key`/`feature`/`feature_key` 定义实体身份，更新已有文件时以库中现有值为准。incoming 数据与库中不一致时 publish 发出告警，由用户决定是否更新。
| related_features | array | | 交叉引用列表，指向相关功能实体（见下方） |
| cases | array | ★ | 用例数组，至少 1 个元素 |

### related_features 交叉引用

每条引用描述当前功能与另一功能的关系，帮助检索时发现关联测试范围：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ★ | 目标功能路径 `<module>/<feature>`（不含 `.json`） |
| relation | string | ★ | 关系类型：`同模块`、`前置依赖`、`数据共享`、`业务关联` |
| note | string | | 一句话说明关系（可选） |

交叉引用由 publish 根据以下信号自动推断并维护：
- 同模块下的其他功能文件 → `同模块`
- 用例 preconditions 中引用了其他模块的功能 → `前置依赖`
- 用例 tp_refs 跨模块引用 → `业务关联`
- 用户在 testpoints.md 或 proposal.md 中显式标注的依赖 → 对应关系类型

交叉引用为累积式——publish 只新增不自动删除。如需清理错误引用，用户手工编辑 feature.json。

### 用例级字段

| 字段 | 类型 | 必填 | 说明 | 来源 |
|------|------|------|------|------|
| id | string | ★ | 源用例编号（source id）；通常来自 generate 的日期+序号格式，用于追溯与去重辅助，不要求跨变更稳定 | testcases.json `id` 直接映射 |
| title | string | ★ | 三段式标题 `{模块}_{功能}_{场景}` | testcases.json `title` |
| priority | string | ★ | P1 / P2 / P3 | testcases.json `priority` |
| type | string | ★ | 冒烟/正向/负向/边界/异常/其他 | testcases.json `type` |
| status | string | ★ | 生命周期状态（见下方） | publish 时设置 |
| feature | string | ★ | 模块名（= 文件级 module） | testcases.json `feature` |
| preconditions | string | | 编号前置条件 `1、xxx\n2、xxx` | testcases.json `preconditions` |
| steps | string | ★ | 编号操作步骤 | testcases.json `steps` |
| expected_result | string | ★ | 编号预期结果 | testcases.json `expected_result` |
| tp_refs | string[] | | 关联当前变更中的 TP_ID 列表，仅用于追溯与检索 | testcases.json `tp_refs` |
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
  "new_cross_refs": [
    { "from": "login/cred", "to": "register/basic", "relation": "前置依赖" }
  ],
  "_context": {
    "source_skill": "testspec-publish",
    "source_change": "user-login",
    "new_cross_refs": [
      { "from": "login/cred", "to": "register/basic", "relation": "前置依赖" }
    ]
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
| new_cross_refs | array | | 本次新建立的交叉引用列表 |
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

增量合并优先级：
1. 同 feature 下 `id` 一致 → 直接更新
2. `id` 不一致但语义上是同一条用例（同模块 + 同功能 + 标题描述的测试场景相同，允许措辞差异）→ 视为同一用例更新
3. 均不匹配 → 作为新增

## 全局索引

路径：`testspec/testlib/index.json`

index.json 是知识库的"目录"——扁平化地列出所有模块、功能和用例摘要，供上游 skill（analysis、points、generate）快速检索已有覆盖，避免逐个扫描 feature.json。

```json
{
  "schema_version": 1,
  "last_updated": "2026-04-14",
  "modules": [
    {
      "module": "登录",
      "module_key": "LOGIN",
      "dir": "login",
      "features": [
        {
          "feature": "凭据验证",
          "feature_key": "CRED",
          "file": "login/cred.json",
          "case_count": 5,
          "by_priority": { "P1": 2, "P2": 2, "P3": 1 },
          "by_status": { "active": 5 },
          "tp_ids": ["TP_LOGIN_CRED_001", "TP_LOGIN_CRED_002", "TP_LOGIN_CRED_100"],
          "last_updated": "2026-04-14",
          "related_features": ["login/phone-login", "register/basic"]
        }
      ],
      "total_cases": 12,
      "last_updated": "2026-04-14"
    }
  ]
}
```

### index.json 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| schema_version | number | 固定 `1` |
| last_updated | string | 最后更新日期 |
| modules[].module | string | 中文模块名 |
| modules[].module_key | string | MODULE 缩写 |
| modules[].dir | string | 模块目录名 |
| modules[].features[] | array | 功能列表 |
| features[].feature | string | 中文功能名 |
| features[].feature_key | string | FEATURE 缩写 |
| features[].file | string | 相对路径（`<module>/<feature>.json`） |
| features[].case_count | number | 用例数 |
| features[].by_priority | object | 按优先级分布 |
| features[].by_status | object | 按状态分布 |
| features[].tp_ids | string[] | 历史用例的 tp_refs 聚合，仅用于模块/功能维度的覆盖范围检索；同一 TP_ID 模式可能来自不同变更，不用于精确去重 |
| features[].last_updated | string | 功能最后更新日期 |
| features[].related_features | string[] | 关联功能路径列表（从 feature.json 同步） |
| modules[].total_cases | number | 模块总用例数 |

### 消费方式

上游 skill 在执行前读取 `index.json`（单次 IO），即可获得：
- 哪些模块/功能已有测试覆盖
- 各功能的用例规模和优先级分布
- 历史用例覆盖过的 TP_ID 列表（用于理解覆盖范围和回归影响）
- 功能间的关联关系（用于发现回归风险）

无需遍历整个 `modules/` 目录。只有当需要读取具体用例内容（如参考步骤写法）时，才按 `file` 路径定点读取 feature.json。

---

## 操作日志

路径：`testspec/testlib/log.md`

log.md 是人可读的操作记录，每次 publish 在文件顶部插入新条目（最新在前）：

```markdown
## 2026-04-14: user-login 入库

**来源**: testspec/changes/user-login
**操作**: 新增 5 条，更新 0 条，废弃 0 条
**涉及模块**: 登录（login/cred, login/phone-login）
**新增交叉引用**: login/cred ↔ register/basic（前置依赖）
```

### 格式规则

- 标题格式：`## YYYY-MM-DD: <change-name> 入库`
- 每条固定 4 个字段：来源、操作、涉及模块、新增交叉引用
- 新增交叉引用为空时写"无"
- 插入位置：文件顶部（`# TestLib 操作日志` 标题之后、已有条目之前）

### 初始内容

首次创建时写入：

```markdown
# TestLib 操作日志

> 每次 testspec-publish 入库后自动追加记录。最新条目在前。

```

---

## 维护脚本

testlib 的长期维护应优先使用确定性脚本。Agent 负责解释结果、给出修复建议，或在用户明确授权后执行修复。

### validate_testlib.py

只读校验 testlib 健康度：

```bash
python skills/testspec-shared/scripts/validate_testlib.py --testlib testspec/testlib
```

校验范围：

- 功能用例文件必填字段、`case_count` 与 `cases` 长度一致性
- 用例必填字段
- 跨功能重复 Case ID
- `related_features` 是否指向存在的功能路径
- `index.json` 是否与 `modules/*/*.json` 一致
- `.testlib.json` 统计是否与 `modules/*/*.json` 一致

脚本输出结构化 JSON 报告；存在 error 时退出码为 `1`。

### rebuild_testlib_index.py

从功能用例文件重建全局索引和统计摘要：

```bash
python skills/testspec-shared/scripts/rebuild_testlib_index.py --testlib testspec/testlib
```

重建内容：

- `index.json`
- `.testlib.json`

该脚本不修改 `modules/*/*.json`，不删除历史用例，不清理 `related_features`。

---

## 变更控制

以下修改属于高风险变更，需同步更新 testspec-publish 和所有消费方：

- `schema_version` 升级
- 必填字段增减
- 目录命名规则变更
- 状态枚举值变更
- 变更日志字段变更
- index.json 结构变更
